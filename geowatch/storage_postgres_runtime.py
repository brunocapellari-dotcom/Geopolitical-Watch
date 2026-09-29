from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Iterable

from .evidence_ledger import build_entry, persist_entry, raw_sha_from_ref
from .migrations import apply_migrations
from .models import Claim, EvidenceRef
from .storage_postgres import PostgresStore, _dict

_SCHEMA_LOCK = threading.Lock()
_SCHEMA_READY: set[str] = set()


def _schema_key(dsn: str) -> str:
    return hashlib.sha256(dsn.encode("utf-8")).hexdigest()


class RuntimePostgresStore(PostgresStore):
    """PostgresStore with idempotent schema/migrations and operational lineage."""

    def __init__(self, dsn: str, schema_path: str | Path = "sql/postgres_postgis.sql") -> None:
        self._runtime_schema_key = _schema_key(dsn)
        super().__init__(dsn, schema_path=schema_path)

    def _init(self, schema_path: Path) -> None:
        key = self._runtime_schema_key
        if key in _SCHEMA_READY:
            return
        with _SCHEMA_LOCK:
            if key in _SCHEMA_READY:
                return
            super()._init(schema_path)
            if hasattr(self, "db"):
                apply_migrations(self.db)
            _SCHEMA_READY.add(key)

    def upsert_evidence(self, evidence: Iterable[EvidenceRef]) -> int:
        rows = list(evidence)
        count = super().upsert_evidence(rows)
        for item in rows:
            persist_entry(
                self.db,
                build_entry(
                    source_id=item.source_id,
                    raw_ref=item.raw_ref,
                    raw_sha256=raw_sha_from_ref(item.raw_ref),
                    evidence_id=item.evidence_id,
                    event_id=item.event_id,
                    metadata={
                        "verification_level": item.verification_level,
                        "evidence_class": item.evidence_class,
                        "relation": item.relation,
                    },
                    created_at=item.observed_at,
                ),
            )
        return count

    def upsert_claims(self, claims: Iterable[Claim]) -> int:
        rows = list(claims)
        count = super().upsert_claims(rows)
        with self.db.cursor() as cur:
            for claim in rows:
                payload = claim.to_dict()
                cur.execute(
                    """
                    SELECT revision, claim_json
                    FROM claim_revisions
                    WHERE claim_id=%s
                    ORDER BY revision DESC
                    LIMIT 1
                    """,
                    (claim.claim_id,),
                )
                previous = cur.fetchone()
                if previous and _dict(previous["claim_json"]) == payload:
                    continue
                revision = int(previous["revision"]) + 1 if previous else 1
                revision_id = "clrev_" + hashlib.sha256(
                    f"{claim.claim_id}|{revision}".encode("utf-8")
                ).hexdigest()[:32]
                cur.execute(
                    """
                    INSERT INTO claim_revisions(
                      revision_id, claim_id, revision, recorded_at, status,
                      confidence, supersedes_claim_id, claim_json
                    ) VALUES(%s,%s,%s,now(),%s,NULL,NULL,%s::jsonb)
                    ON CONFLICT(revision_id) DO NOTHING
                    """,
                    (
                        revision_id,
                        claim.claim_id,
                        revision,
                        claim.status,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )
        self.db.commit()
        return count

    def enqueue_dead_letter(
        self,
        *,
        dead_letter_id: str,
        source_id: str,
        failed_at: str,
        failure_class: str,
        error_type: str | None,
        error_message: str | None,
        request: dict[str, object] | None,
        payload_ref: str | None,
        attempts: int,
    ) -> bool:
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collector_dead_letter(
                  dead_letter_id, source_id, failed_at, failure_class,
                  error_type, error_message, request_json, payload_ref, attempts
                ) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                ON CONFLICT(dead_letter_id) DO UPDATE SET
                  attempts=GREATEST(collector_dead_letter.attempts, EXCLUDED.attempts),
                  error_type=EXCLUDED.error_type,
                  error_message=EXCLUDED.error_message
                RETURNING dead_letter_id
                """,
                (
                    dead_letter_id,
                    source_id,
                    failed_at,
                    failure_class,
                    error_type,
                    error_message,
                    json.dumps(request or {}, ensure_ascii=False),
                    payload_ref,
                    attempts,
                ),
            )
            inserted = cur.fetchone() is not None
        self.db.commit()
        return inserted

    def pending_dead_letters(self, *, limit: int = 100) -> list[dict[str, object]]:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM collector_dead_letter
                WHERE status='pending'
                ORDER BY failed_at
                LIMIT %s
                """,
                (max(1, min(limit, 1000)),),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def mark_dead_letter_replayed(self, dead_letter_id: str, *, replayed_at: str) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE collector_dead_letter
                SET status='replayed', replayed_at=%s::timestamptz
                WHERE dead_letter_id=%s
                """,
                (replayed_at, dead_letter_id),
            )
        self.db.commit()

    def record_run(
        self,
        *,
        run_id: str,
        source_id: str,
        started_at: str,
        finished_at: str,
        status: str,
        records: int = 0,
        request: dict | None = None,
        error: str | None = None,
    ) -> None:
        super().record_run(
            run_id=run_id,
            source_id=source_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            records=records,
            request=request,
            error=error,
        )
        success = status == "ok"
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO source_runtime_state(
                  source_id, operational_state, last_success_at, last_failure_at,
                  consecutive_failures, circuit_open_until
                ) VALUES(
                  %s,
                  %s,
                  CASE WHEN %s THEN %s::timestamptz ELSE NULL END,
                  CASE WHEN %s THEN NULL ELSE %s::timestamptz END,
                  CASE WHEN %s THEN 0 ELSE 1 END,
                  NULL
                )
                ON CONFLICT(source_id) DO UPDATE SET
                  operational_state = CASE
                    WHEN %s THEN 'HEALTHY'
                    WHEN source_runtime_state.consecutive_failures + 1 >= 5 THEN 'BROKEN'
                    ELSE 'DEGRADED'
                  END,
                  last_success_at = CASE WHEN %s THEN EXCLUDED.last_success_at ELSE source_runtime_state.last_success_at END,
                  last_failure_at = CASE WHEN %s THEN source_runtime_state.last_failure_at ELSE EXCLUDED.last_failure_at END,
                  consecutive_failures = CASE WHEN %s THEN 0 ELSE source_runtime_state.consecutive_failures + 1 END,
                  updated_at=now()
                """,
                (
                    source_id,
                    "HEALTHY" if success else "DEGRADED",
                    success,
                    finished_at,
                    success,
                    finished_at,
                    success,
                    success,
                    success,
                    success,
                    success,
                ),
            )
        self.db.commit()

    def get_source_runtime_state(self, source_id: str) -> dict[str, object] | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM source_runtime_state WHERE source_id=%s", (source_id,))
            row = cur.fetchone()
        return dict(row) if row else None


def reset_schema_cache_for_tests() -> None:
    with _SCHEMA_LOCK:
        _SCHEMA_READY.clear()

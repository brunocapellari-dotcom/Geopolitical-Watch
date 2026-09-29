from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class EvidenceLedgerEntry:
    ledger_id: str
    source_id: str
    created_at: str
    raw_ref: str | None = None
    raw_sha256: str | None = None
    extraction_id: str | None = None
    evidence_id: str | None = None
    claim_id: str | None = None
    event_id: str | None = None
    metadata: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def deterministic_ledger_id(
    *,
    source_id: str,
    raw_ref: str | None = None,
    extraction_id: str | None = None,
    evidence_id: str | None = None,
    claim_id: str | None = None,
    event_id: str | None = None,
) -> str:
    seed = "|".join([
        source_id.strip(),
        raw_ref or "",
        extraction_id or "",
        evidence_id or "",
        claim_id or "",
        event_id or "",
    ])
    return "ledger_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def build_entry(
    *,
    source_id: str,
    raw_ref: str | None = None,
    raw_sha256: str | None = None,
    extraction_id: str | None = None,
    evidence_id: str | None = None,
    claim_id: str | None = None,
    event_id: str | None = None,
    metadata: dict[str, object] | None = None,
    created_at: str | None = None,
) -> EvidenceLedgerEntry:
    if not source_id.strip():
        raise ValueError("source_id is required")
    if raw_sha256 is not None and (
        len(raw_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in raw_sha256.casefold())
    ):
        raise ValueError("raw_sha256 must be a 64-character hexadecimal digest")
    if not any((raw_ref, extraction_id, evidence_id, claim_id, event_id)):
        raise ValueError("ledger entry requires at least one lineage reference")
    return EvidenceLedgerEntry(
        ledger_id=deterministic_ledger_id(
            source_id=source_id,
            raw_ref=raw_ref,
            extraction_id=extraction_id,
            evidence_id=evidence_id,
            claim_id=claim_id,
            event_id=event_id,
        ),
        source_id=source_id,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        raw_ref=raw_ref,
        raw_sha256=raw_sha256.casefold() if raw_sha256 else None,
        extraction_id=extraction_id,
        evidence_id=evidence_id,
        claim_id=claim_id,
        event_id=event_id,
        metadata=dict(metadata or {}),
    )


def persist_entry(db, entry: EvidenceLedgerEntry) -> bool:  # type: ignore[no-untyped-def]
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO evidence_ledger(
              ledger_id, source_id, raw_ref, raw_sha256, extraction_id,
              evidence_id, claim_id, event_id, created_at, metadata_json
            ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT(ledger_id) DO NOTHING
            RETURNING ledger_id
            """,
            (
                entry.ledger_id,
                entry.source_id,
                entry.raw_ref,
                entry.raw_sha256,
                entry.extraction_id,
                entry.evidence_id,
                entry.claim_id,
                entry.event_id,
                entry.created_at,
                json.dumps(entry.metadata or {}, ensure_ascii=False),
            ),
        )
        inserted = cur.fetchone() is not None
    db.commit()
    return inserted


def raw_sha_from_ref(raw_ref: str | None) -> str | None:
    if not raw_ref:
        return None
    leaf = raw_ref.rsplit("/", 1)[-1]
    digest = leaf.split(".", 1)[0]
    value = digest.casefold()
    if len(value) == 64 and all(ch in "0123456789abcdef" for ch in value):
        return value
    return None

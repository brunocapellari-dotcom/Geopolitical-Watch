from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .core import EventCluster, deterministic_cluster_id, score_cluster
from .models import Claim, ConflictEpisode, Entity, Event, EvidenceRef, Relationship
from .temporal import canonical_payload


class PostgresStore:
    """Production PostgreSQL/PostGIS store.

    psycopg is imported lazily so the zero-cost SQLite/test runtime does not require
    PostgreSQL dependencies. Set GEOWATCH_DB_URL to a postgresql:// DSN and install
    the `postgres` optional dependency to activate this backend.
    """

    backend = "postgresql-postgis"

    def __init__(self, dsn: str, schema_path: str | Path = "sql/postgres_postgis.sql") -> None:
        try:
            import psycopg  # type: ignore
            from psycopg.rows import dict_row  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PostgreSQL backend requires: pip install 'geopolitical-watch[postgres]'") from exc
        self.db = psycopg.connect(dsn, row_factory=dict_row)
        self._init(Path(schema_path))

    def _init(self, schema_path: Path) -> None:
        with self.db.cursor() as cur:
            cur.execute(schema_path.read_text(encoding="utf-8"))
        self.db.commit()

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _record_version(self, cur, object_type: str, object_id: str, payload: dict, *, recorded_at: str | None = None) -> bool:
        raw, digest = canonical_payload(payload)
        cur.execute(
            """SELECT payload_sha256 FROM object_versions
               WHERE object_type=%s AND object_id=%s
               ORDER BY recorded_at DESC, version_id DESC LIMIT 1""",
            (object_type, object_id),
        )
        latest = cur.fetchone()
        if latest and latest["payload_sha256"] == digest:
            return False
        cur.execute(
            """INSERT INTO object_versions(object_type, object_id, recorded_at, payload_sha256, payload_json)
               VALUES(%s,%s,COALESCE(%s::timestamptz,now()),%s,%s::jsonb)
               ON CONFLICT DO NOTHING
               RETURNING version_id""",
            (object_type, object_id, recorded_at, digest, raw),
        )
        return cur.fetchone() is not None

    def record_versions(
        self,
        object_type: str,
        rows: Iterable[tuple[str, dict]],
        *,
        recorded_at: str | None = None,
    ) -> int:
        inserted = 0
        with self.db.cursor() as cur:
            for object_id, payload in rows:
                inserted += int(self._record_version(cur, object_type, object_id, payload, recorded_at=recorded_at))
        self.db.commit()
        return inserted

    def list_versions(self, object_type: str, object_id: str) -> list[dict]:
        with self.db.cursor() as cur:
            cur.execute(
                """SELECT object_type, object_id, recorded_at, payload_sha256, payload_json
                   FROM object_versions
                   WHERE object_type=%s AND object_id=%s
                   ORDER BY recorded_at, version_id""",
                (object_type, object_id),
            )
            rows = cur.fetchall()
        return [
            {
                "object_type": row["object_type"],
                "object_id": row["object_id"],
                "recorded_at": _iso(row["recorded_at"]),
                "payload_sha256": row["payload_sha256"],
                "payload": _dict(row["payload_json"]),
            }
            for row in rows
        ]

    def snapshot_as_of(self, as_of: str, *, object_type: str | None = None, limit: int = 5000) -> list[dict]:
        clauses = ["recorded_at <= %s::timestamptz"]
        params: list[object] = [as_of]
        if object_type:
            clauses.append("object_type=%s")
            params.append(object_type)
        params.append(max(1, min(limit, 10000)))
        with self.db.cursor() as cur:
            cur.execute(
                f"""SELECT object_type, object_id, recorded_at, payload_sha256, payload_json
                    FROM (
                      SELECT DISTINCT ON (object_type, object_id)
                        object_type, object_id, recorded_at, payload_sha256, payload_json, version_id
                      FROM object_versions
                      WHERE {' AND '.join(clauses)}
                      ORDER BY object_type, object_id, recorded_at DESC, version_id DESC
                    ) latest
                    ORDER BY object_type, object_id
                    LIMIT %s""",
                params,
            )
            rows = cur.fetchall()
        return [
            {
                "object_type": row["object_type"],
                "object_id": row["object_id"],
                "recorded_at": _iso(row["recorded_at"]),
                "payload_sha256": row["payload_sha256"],
                "payload": _dict(row["payload_json"]),
            }
            for row in rows
        ]

    # --- events --------------------------------------------------------------
    def upsert_events(self, events: list[Event]) -> int:
        with self.db.cursor() as cur:
            for event in events:
                self._record_version(cur, "event", event.event_id, event.to_dict(), recorded_at=event.collected_at)
                cur.execute("""
                INSERT INTO events(event_id, reference_at, source_id, verification_level, country, latitude, longitude, geom, event_json)
                VALUES(%s,%s,%s,%s,%s,%s,%s,
                  CASE WHEN %s IS NOT NULL AND %s IS NOT NULL THEN ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography ELSE NULL END,
                  %s::jsonb)
                ON CONFLICT(event_id) DO UPDATE SET reference_at=EXCLUDED.reference_at, source_id=EXCLUDED.source_id,
                  verification_level=EXCLUDED.verification_level, country=EXCLUDED.country,
                  latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude, geom=EXCLUDED.geom,
                  event_json=EXCLUDED.event_json, updated_at=now()
                """, (
                    event.event_id, event.reference_at, event.source_id, event.verification_level, event.country,
                    event.latitude, event.longitude, event.latitude, event.longitude, event.longitude, event.latitude,
                    self._json(event.to_dict()),
                ))
        self.db.commit()
        return len(events)

    def load_events_since(self, reference_at: str) -> list[Event]:
        with self.db.cursor() as cur:
            cur.execute("SELECT event_json FROM events WHERE reference_at >= %s::timestamptz ORDER BY reference_at", (reference_at,))
            rows = cur.fetchall()
        return [Event.from_dict(_dict(row["event_json"])) for row in rows]

    def load_events_by_ids(self, event_ids: Iterable[str]) -> list[Event]:
        ids = list(dict.fromkeys(event_ids))
        if not ids:
            return []
        with self.db.cursor() as cur:
            cur.execute("SELECT event_json FROM events WHERE event_id = ANY(%s)", (ids,))
            rows = cur.fetchall()
        return [Event.from_dict(_dict(row["event_json"])) for row in rows]

    def list_events(self, *, since: str | None = None, country: str | None = None, limit: int = 200) -> list[dict]:
        clauses = ["TRUE"]
        params: list[object] = []
        if since:
            clauses.append("reference_at >= %s::timestamptz")
            params.append(since)
        if country:
            clauses.append("country = %s")
            params.append(country)
        params.append(max(1, min(limit, 1000)))
        with self.db.cursor() as cur:
            cur.execute(f"SELECT event_json FROM events WHERE {' AND '.join(clauses)} ORDER BY reference_at DESC LIMIT %s", params)
            rows = cur.fetchall()
        return [_dict(row["event_json"]) for row in rows]

    # --- reports/clusters ----------------------------------------------------
    def upsert_clusters(self, clusters: list[EventCluster], generated_at: str) -> int:
        with self.db.cursor() as cur:
            for cluster in clusters:
                payload = {**cluster.to_dict(), "priority_score": score_cluster(cluster), "priority_method_version": "geowatch-priority-v0.4"}
                cur.execute("""
                INSERT INTO clusters(cluster_id, generated_at, priority_score, cluster_json)
                VALUES(%s,%s,%s,%s::jsonb)
                ON CONFLICT(cluster_id) DO UPDATE SET generated_at=EXCLUDED.generated_at,
                  priority_score=EXCLUDED.priority_score, cluster_json=EXCLUDED.cluster_json, updated_at=now()
                """, (deterministic_cluster_id(cluster), generated_at, score_cluster(cluster), self._json(payload)))
        self.db.commit()
        return len(clusters)

    def upsert_report(self, report: dict, markdown: str) -> str:
        with self.db.cursor() as cur:
            cur.execute("""
            INSERT INTO reports(report_id, generated_at, report_type, report_json, report_markdown)
            VALUES(%s,%s,%s,%s::jsonb,%s)
            ON CONFLICT(report_id) DO UPDATE SET report_json=EXCLUDED.report_json,
              report_markdown=EXCLUDED.report_markdown, updated_at=now()
            """, (report["report_id"], report["generated_at"], report["report_type"], self._json(report), markdown))
        self.db.commit()
        return str(report["report_id"])

    def latest_report(self, report_type: str | None = None) -> dict | None:
        with self.db.cursor() as cur:
            if report_type:
                cur.execute("SELECT report_json FROM reports WHERE report_type=%s ORDER BY generated_at DESC LIMIT 1", (report_type,))
            else:
                cur.execute("SELECT report_json FROM reports ORDER BY generated_at DESC LIMIT 1")
            row = cur.fetchone()
        return _dict(row["report_json"]) if row else None

    # --- entities/evidence/claims/episodes ----------------------------------
    def upsert_entities(self, entities: Iterable[Entity]) -> int:
        rows = list(entities)
        with self.db.cursor() as cur:
            for entity in rows:
                self._record_version(cur, "entity", entity.entity_id, entity.to_dict())
                cur.execute("""
                INSERT INTO entities(entity_id, entity_type, canonical_name, country, latitude, longitude, geom, entity_json)
                VALUES(%s,%s,%s,%s,%s,%s,
                  CASE WHEN %s IS NOT NULL AND %s IS NOT NULL THEN ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography ELSE NULL END,
                  %s::jsonb)
                ON CONFLICT(entity_id) DO UPDATE SET entity_type=EXCLUDED.entity_type,
                  canonical_name=EXCLUDED.canonical_name, country=EXCLUDED.country,
                  latitude=COALESCE(EXCLUDED.latitude, entities.latitude), longitude=COALESCE(EXCLUDED.longitude, entities.longitude),
                  geom=COALESCE(EXCLUDED.geom, entities.geom), entity_json=EXCLUDED.entity_json, updated_at=now()
                """, (
                    entity.entity_id, entity.entity_type, entity.canonical_name, entity.country,
                    entity.latitude, entity.longitude, entity.latitude, entity.longitude, entity.longitude, entity.latitude,
                    self._json(entity.to_dict()),
                ))
        self.db.commit()
        return len(rows)

    def load_entities(self) -> list[Entity]:
        with self.db.cursor() as cur:
            cur.execute("SELECT entity_json FROM entities")
            rows = cur.fetchall()
        return [Entity.from_dict(_dict(row["entity_json"])) for row in rows]

    def upsert_relationships(self, relationships: Iterable[Relationship]) -> int:
        rows = list(relationships)
        with self.db.cursor() as cur:
            for relationship in rows:
                self._record_version(cur, "relationship", relationship.relationship_id, relationship.to_dict(), recorded_at=relationship.last_seen_at)
                cur.execute("""
                INSERT INTO relationships(
                  relationship_id, source_entity_id, target_entity_id, relationship_type, semantic_class,
                  first_seen_at, last_seen_at, valid_from, valid_to, confidence, relationship_json
                ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT(relationship_id) DO UPDATE SET source_entity_id=EXCLUDED.source_entity_id,
                  target_entity_id=EXCLUDED.target_entity_id, relationship_type=EXCLUDED.relationship_type,
                  semantic_class=EXCLUDED.semantic_class,
                  first_seen_at=EXCLUDED.first_seen_at,
                  last_seen_at=EXCLUDED.last_seen_at,
                  valid_from=EXCLUDED.valid_from, valid_to=EXCLUDED.valid_to,
                  confidence=EXCLUDED.confidence, relationship_json=EXCLUDED.relationship_json, updated_at=now()
                """, (
                    relationship.relationship_id, relationship.source_entity_id, relationship.target_entity_id,
                    relationship.relationship_type, relationship.semantic_class, relationship.first_seen_at,
                    relationship.last_seen_at, relationship.valid_from, relationship.valid_to, relationship.confidence,
                    self._json(relationship.to_dict()),
                ))
        self.db.commit()
        return len(rows)

    def load_relationships(self, *, entity_id: str | None = None, relationship_type: str | None = None) -> list[Relationship]:
        clauses = ["TRUE"]
        params: list[object] = []
        if entity_id:
            clauses.append("(source_entity_id=%s OR target_entity_id=%s)")
            params.extend([entity_id, entity_id])
        if relationship_type:
            clauses.append("relationship_type=%s")
            params.append(relationship_type)
        with self.db.cursor() as cur:
            cur.execute(f"SELECT relationship_json FROM relationships WHERE {' AND '.join(clauses)} ORDER BY last_seen_at DESC", params)
            rows = cur.fetchall()
        return [Relationship.from_dict(_dict(row["relationship_json"])) for row in rows]

    def upsert_evidence(self, evidence: Iterable[EvidenceRef]) -> int:
        rows = list(evidence)
        with self.db.cursor() as cur:
            for item in rows:
                self._record_version(cur, "evidence", item.evidence_id, item.to_dict(), recorded_at=item.observed_at)
                cur.execute("""
                INSERT INTO evidence(evidence_id, event_id, source_id, verification_level, relation, observed_at, evidence_json)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT(evidence_id) DO UPDATE SET relation=EXCLUDED.relation,
                  evidence_json=EXCLUDED.evidence_json, updated_at=now()
                """, (item.evidence_id, item.event_id, item.source_id, item.verification_level, item.relation, item.observed_at, self._json(item.to_dict())))
        self.db.commit()
        return len(rows)

    def load_evidence(self, *, episode_id: str | None = None) -> list[EvidenceRef]:
        with self.db.cursor() as cur:
            if episode_id:
                cur.execute("""
                SELECT DISTINCT e.evidence_json FROM evidence e
                JOIN claim_evidence ce ON ce.evidence_id=e.evidence_id
                JOIN claims c ON c.claim_id=ce.claim_id WHERE c.episode_id=%s
                """, (episode_id,))
            else:
                cur.execute("SELECT evidence_json FROM evidence")
            rows = cur.fetchall()
        return [EvidenceRef.from_dict(_dict(row["evidence_json"])) for row in rows]

    def upsert_episodes(self, episodes: Iterable[ConflictEpisode]) -> int:
        rows = list(episodes)
        with self.db.cursor() as cur:
            for episode in rows:
                self._record_version(cur, "episode", episode.episode_id, episode.to_dict(), recorded_at=episode.last_updated_at)
                strength = episode.evidence_strength.overall_index if episode.evidence_strength else None
                primary_country = episode.countries[0] if episode.countries else None
                cur.execute("""
                INSERT INTO episodes(episode_id, state, started_at, last_updated_at, primary_country, evidence_strength_index, episode_json)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT(episode_id) DO UPDATE SET state=EXCLUDED.state, last_updated_at=EXCLUDED.last_updated_at,
                  primary_country=EXCLUDED.primary_country, evidence_strength_index=EXCLUDED.evidence_strength_index,
                  episode_json=EXCLUDED.episode_json, updated_at=now()
                """, (episode.episode_id, episode.state, episode.started_at, episode.last_updated_at, primary_country, strength, self._json(episode.to_dict())))
                for event_id in episode.event_ids:
                    cur.execute("INSERT INTO episode_events(episode_id,event_id) VALUES(%s,%s) ON CONFLICT DO NOTHING", (episode.episode_id, event_id))
        self.db.commit()
        return len(rows)

    def upsert_claims(self, claims: Iterable[Claim]) -> int:
        rows = list(claims)
        with self.db.cursor() as cur:
            for claim in rows:
                self._record_version(cur, "claim", claim.claim_id, claim.to_dict(), recorded_at=claim.last_seen_at)
                cur.execute("""
                INSERT INTO claims(claim_id, episode_id, claim_type, topic_key, status, first_seen_at, last_seen_at, claim_json)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT(claim_id) DO UPDATE SET episode_id=EXCLUDED.episode_id, claim_type=EXCLUDED.claim_type,
                  topic_key=EXCLUDED.topic_key, status=EXCLUDED.status, last_seen_at=EXCLUDED.last_seen_at,
                  claim_json=EXCLUDED.claim_json, updated_at=now()
                """, (claim.claim_id, claim.episode_id, claim.claim_type, claim.topic_key, claim.status, claim.first_seen_at, claim.last_seen_at, self._json(claim.to_dict())))
                for evidence_id in claim.evidence_ids:
                    cur.execute("INSERT INTO claim_evidence(claim_id,evidence_id) VALUES(%s,%s) ON CONFLICT DO NOTHING", (claim.claim_id, evidence_id))
        self.db.commit()
        return len(rows)

    def load_claims(self, *, episode_id: str | None = None) -> list[Claim]:
        with self.db.cursor() as cur:
            if episode_id:
                cur.execute("SELECT claim_json FROM claims WHERE episode_id=%s ORDER BY first_seen_at", (episode_id,))
            else:
                cur.execute("SELECT claim_json FROM claims ORDER BY first_seen_at")
            rows = cur.fetchall()
        return [Claim.from_dict(_dict(row["claim_json"])) for row in rows]

    def load_episodes(self, *, since: str | None = None, states: Iterable[str] | None = None, limit: int | None = None) -> list[ConflictEpisode]:
        clauses = ["TRUE"]
        params: list[object] = []
        if since:
            clauses.append("last_updated_at >= %s::timestamptz")
            params.append(since)
        state_values = list(states or ())
        if state_values:
            clauses.append("state = ANY(%s)")
            params.append(state_values)
        sql = f"SELECT episode_json FROM episodes WHERE {' AND '.join(clauses)} ORDER BY last_updated_at DESC"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(max(1, min(limit, 5000)))
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [ConflictEpisode.from_dict(_dict(row["episode_json"])) for row in rows]

    def get_episode(self, episode_id: str) -> ConflictEpisode | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT episode_json FROM episodes WHERE episode_id=%s", (episode_id,))
            row = cur.fetchone()
        return ConflictEpisode.from_dict(_dict(row["episode_json"])) if row else None

    def list_episode_records(self, *, country: str | None = None, state: str | None = None, since: str | None = None, min_strength: int | None = None, limit: int = 100) -> list[dict]:
        clauses = ["TRUE"]
        params: list[object] = []
        if country:
            clauses.append("primary_country=%s")
            params.append(country)
        if state:
            clauses.append("state=%s")
            params.append(state)
        if since:
            clauses.append("last_updated_at >= %s::timestamptz")
            params.append(since)
        if min_strength is not None:
            clauses.append("COALESCE(evidence_strength_index,0) >= %s")
            params.append(int(min_strength))
        params.append(max(1, min(limit, 1000)))
        with self.db.cursor() as cur:
            cur.execute(f"SELECT episode_json FROM episodes WHERE {' AND '.join(clauses)} ORDER BY last_updated_at DESC LIMIT %s", params)
            rows = cur.fetchall()
        return [_dict(row["episode_json"]) for row in rows]

    def record_changes(self, changes: Iterable[dict[str, object]]) -> int:
        rows = list(changes)
        with self.db.cursor() as cur:
            for change in rows:
                cur.execute("INSERT INTO episode_changes(episode_id,occurred_at,change_type,change_json) VALUES(%s,%s,%s,%s::jsonb)", (
                    change["episode_id"], change.get("at") or change.get("occurred_at"), change["change_type"], self._json(change),
                ))
        self.db.commit()
        return len(rows)

    def changes_since(self, since: str, *, limit: int = 500) -> list[dict]:
        with self.db.cursor() as cur:
            cur.execute("SELECT change_json FROM episode_changes WHERE occurred_at >= %s::timestamptz ORDER BY occurred_at LIMIT %s", (since, max(1, min(limit, 5000))))
            rows = cur.fetchall()
        return [_dict(row["change_json"]) for row in rows]

    # --- collection audit ----------------------------------------------------
    def get_checkpoint(self, source_id: str) -> dict | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM source_checkpoints WHERE source_id=%s", (source_id,))
            row = cur.fetchone()
        if not row:
            return None
        return {
            "source_id": row["source_id"],
            "last_success_at": _iso(row["last_success_at"]),
            "last_reference_at": _iso(row["last_reference_at"]),
            "cursor": _dict(row["cursor_json"]) if row.get("cursor_json") else None,
            "updated_at": _iso(row["updated_at"]),
        }

    def update_checkpoint(self, source_id: str, *, last_success_at: str, last_reference_at: str | None = None, cursor: dict | None = None) -> None:
        with self.db.cursor() as cur:
            cur.execute("""
            INSERT INTO source_checkpoints(source_id,last_success_at,last_reference_at,cursor_json)
            VALUES(%s,%s,%s,%s::jsonb)
            ON CONFLICT(source_id) DO UPDATE SET last_success_at=EXCLUDED.last_success_at,
              last_reference_at=COALESCE(EXCLUDED.last_reference_at, source_checkpoints.last_reference_at),
              cursor_json=EXCLUDED.cursor_json, updated_at=now()
            """, (source_id, last_success_at, last_reference_at, self._json(cursor) if cursor is not None else None))
        self.db.commit()

    def record_run(self, *, run_id: str, source_id: str, started_at: str, finished_at: str, status: str, records: int = 0, request: dict | None = None, error: str | None = None) -> None:
        with self.db.cursor() as cur:
            cur.execute("""
            INSERT INTO collector_runs(run_id,source_id,started_at,finished_at,status,records,request_json,error)
            VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            ON CONFLICT(run_id) DO UPDATE SET finished_at=EXCLUDED.finished_at,status=EXCLUDED.status,
              records=EXCLUDED.records,request_json=EXCLUDED.request_json,error=EXCLUDED.error,updated_at=now()
            """, (run_id, source_id, started_at, finished_at, status, records, self._json(request) if request else None, error))
        self.db.commit()

    def recent_runs(self, *, limit: int = 100) -> list[dict]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM collector_runs ORDER BY started_at DESC LIMIT %s", (max(1, min(limit, 1000)),))
            rows = cur.fetchall()
        return [{key: (_iso(value) if hasattr(value, "isoformat") else value) for key, value in row.items()} for row in rows]

    def add_artifact(self, *, artifact_id: str, source_id: str, sha256: str, collected_at: str, observed_url: str | None, path: str, bytes_count: int) -> None:
        with self.db.cursor() as cur:
            cur.execute("""
            INSERT INTO raw_artifacts(artifact_id,source_id,sha256,collected_at,observed_url,path,bytes)
            VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source_id,sha256) DO NOTHING
            """, (artifact_id, source_id, sha256, collected_at, observed_url, path, bytes_count))
        self.db.commit()

    # --- alerts --------------------------------------------------------------
    def enqueue_alert(self, alert: dict[str, object]) -> bool:
        with self.db.cursor() as cur:
            cur.execute("""
            INSERT INTO alert_outbox(alert_id,episode_id,created_at,severity,policy_id,payload_json)
            VALUES(%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT(alert_id) DO NOTHING
            RETURNING alert_id
            """, (alert["alert_id"], alert["episode_id"], alert["created_at"], alert["severity"], alert["policy_id"], self._json(alert)))
            inserted = cur.fetchone() is not None
        self.db.commit()
        return inserted

    def pending_alerts(self, *, limit: int = 100) -> list[dict]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM alert_outbox WHERE status='pending' ORDER BY created_at LIMIT %s", (max(1, min(limit, 1000)),))
            rows = cur.fetchall()
        return [dict(row) | {"payload": _dict(row["payload_json"])} for row in rows]

    def mark_alert(self, alert_id: str, *, status: str, error: str | None = None, delivered_at: str | None = None) -> None:
        with self.db.cursor() as cur:
            cur.execute("""
            UPDATE alert_outbox SET status=%s, attempts=attempts+1, last_error=%s,
              delivered_at=COALESCE(%s::timestamptz, delivered_at) WHERE alert_id=%s
            """, (status, error, delivered_at, alert_id))
        self.db.commit()

    def close(self) -> None:
        self.db.close()


def _dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)  # type: ignore[arg-type]


def _iso(value: object) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)

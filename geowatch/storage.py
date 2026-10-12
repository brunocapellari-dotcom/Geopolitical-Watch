from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .core import EventCluster, deterministic_cluster_id, score_cluster
from .models import Claim, ConflictEpisode, Entity, Event, EvidenceRef, Relationship
from .temporal import canonical_payload


class SQLiteStore:
    """Development/reference store.

    SQLite remains intentionally supported for zero-cost local execution and tests.
    Production deployments may use the PostgresStore adapter; both implement the
    episode/event contract used by the API and pipeline.
    """

    def __init__(self, path: str | Path = "data/geowatch.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS events (
          event_id TEXT PRIMARY KEY,
          reference_at TEXT NOT NULL,
          source_id TEXT NOT NULL,
          verification_level TEXT NOT NULL,
          country TEXT,
          event_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_events_reference ON events(reference_at);
        CREATE INDEX IF NOT EXISTS idx_events_country ON events(country);

        CREATE TABLE IF NOT EXISTS clusters (
          cluster_id TEXT PRIMARY KEY,
          generated_at TEXT NOT NULL,
          priority_score INTEGER NOT NULL,
          cluster_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_clusters_priority ON clusters(priority_score);

        CREATE TABLE IF NOT EXISTS reports (
          report_id TEXT PRIMARY KEY,
          generated_at TEXT NOT NULL,
          report_type TEXT NOT NULL,
          report_json TEXT NOT NULL,
          report_markdown TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS source_checkpoints (
          source_id TEXT PRIMARY KEY,
          last_success_at TEXT,
          last_reference_at TEXT,
          cursor_json TEXT,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS collector_runs (
          run_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          started_at TEXT NOT NULL,
          finished_at TEXT NOT NULL,
          status TEXT NOT NULL,
          records INTEGER NOT NULL DEFAULT 0,
          request_json TEXT,
          error TEXT,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_runs_source_started ON collector_runs(source_id, started_at);
        CREATE TABLE IF NOT EXISTS raw_artifacts (
          artifact_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          collected_at TEXT NOT NULL,
          observed_url TEXT,
          path TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          UNIQUE(source_id, sha256)
        );

        CREATE TABLE IF NOT EXISTS entities (
          entity_id TEXT PRIMARY KEY,
          entity_type TEXT NOT NULL,
          canonical_name TEXT NOT NULL,
          country TEXT,
          latitude REAL,
          longitude REAL,
          entity_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
        CREATE INDEX IF NOT EXISTS idx_entities_country ON entities(country);

        CREATE TABLE IF NOT EXISTS relationships (
          relationship_id TEXT PRIMARY KEY,
          source_entity_id TEXT NOT NULL,
          target_entity_id TEXT NOT NULL,
          relationship_type TEXT NOT NULL,
          semantic_class TEXT NOT NULL,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          valid_from TEXT,
          valid_to TEXT,
          confidence REAL,
          relationship_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_entity_id);
        CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_entity_id);
        CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type);
        CREATE INDEX IF NOT EXISTS idx_relationships_validity ON relationships(valid_from, valid_to);

        CREATE TABLE IF NOT EXISTS episodes (
          episode_id TEXT PRIMARY KEY,
          state TEXT NOT NULL,
          started_at TEXT NOT NULL,
          last_updated_at TEXT NOT NULL,
          primary_country TEXT,
          evidence_strength_index INTEGER,
          episode_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_episodes_state_updated ON episodes(state, last_updated_at);
        CREATE INDEX IF NOT EXISTS idx_episodes_country ON episodes(primary_country);

        CREATE TABLE IF NOT EXISTS episode_events (
          episode_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(episode_id, event_id)
        );
        CREATE INDEX IF NOT EXISTS idx_episode_events_event ON episode_events(event_id);

        CREATE TABLE IF NOT EXISTS claims (
          claim_id TEXT PRIMARY KEY,
          episode_id TEXT NOT NULL,
          claim_type TEXT NOT NULL,
          topic_key TEXT NOT NULL,
          status TEXT NOT NULL,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          claim_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_claims_episode ON claims(episode_id);
        CREATE INDEX IF NOT EXISTS idx_claims_topic ON claims(topic_key);

        CREATE TABLE IF NOT EXISTS evidence (
          evidence_id TEXT PRIMARY KEY,
          event_id TEXT NOT NULL,
          source_id TEXT NOT NULL,
          verification_level TEXT NOT NULL,
          relation TEXT NOT NULL,
          observed_at TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_event ON evidence(event_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_observed ON evidence(observed_at);

        CREATE TABLE IF NOT EXISTS claim_evidence (
          claim_id TEXT NOT NULL,
          evidence_id TEXT NOT NULL,
          PRIMARY KEY(claim_id, evidence_id)
        );

        CREATE TABLE IF NOT EXISTS episode_changes (
          change_id INTEGER PRIMARY KEY AUTOINCREMENT,
          episode_id TEXT NOT NULL,
          occurred_at TEXT NOT NULL,
          change_type TEXT NOT NULL,
          change_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_changes_at ON episode_changes(occurred_at);
        CREATE INDEX IF NOT EXISTS idx_changes_episode ON episode_changes(episode_id, occurred_at);

        CREATE TABLE IF NOT EXISTS object_versions (
          version_id INTEGER PRIMARY KEY AUTOINCREMENT,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          recorded_at TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          UNIQUE(object_type, object_id, recorded_at, payload_sha256)
        );
        CREATE INDEX IF NOT EXISTS idx_object_versions_asof ON object_versions(object_type, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_object_versions_object ON object_versions(object_type, object_id, recorded_at);

        CREATE TABLE IF NOT EXISTS alert_outbox (
          alert_id TEXT PRIMARY KEY,
          episode_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          severity TEXT NOT NULL,
          policy_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          payload_json TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0,
          last_error TEXT,
          delivered_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_alert_outbox_status ON alert_outbox(status, created_at);
        """)
        self.db.execute("INSERT OR IGNORE INTO schema_migrations(version, name) VALUES(1, 'v0.4 baseline')")
        self.db.execute("INSERT OR IGNORE INTO schema_migrations(version, name) VALUES(2, 'v0.5 episode convergence')")
        self.db.execute("INSERT OR IGNORE INTO schema_migrations(version, name) VALUES(4, 'v0.16 temporal relationships')")
        self.db.execute("INSERT OR IGNORE INTO schema_migrations(version, name) VALUES(5, 'go-live immutable object versions')")
        self.db.commit()

    def _record_version(self, object_type: str, object_id: str, payload: dict, *, recorded_at: str | None = None) -> bool:
        raw, digest = canonical_payload(payload)
        latest = self.db.execute(
            """SELECT payload_sha256 FROM object_versions
               WHERE object_type=? AND object_id=?
               ORDER BY recorded_at DESC, version_id DESC LIMIT 1""",
            (object_type, object_id),
        ).fetchone()
        if latest and latest["payload_sha256"] == digest:
            return False
        when = recorded_at or datetime.now(timezone.utc).isoformat()
        before = self.db.total_changes
        self.db.execute(
            """INSERT OR IGNORE INTO object_versions(object_type, object_id, recorded_at, payload_sha256, payload_json)
               VALUES(?,?,?,?,?)""",
            (object_type, object_id, when, digest, raw),
        )
        return self.db.total_changes > before

    def record_versions(
        self,
        object_type: str,
        rows: Iterable[tuple[str, dict]],
        *,
        recorded_at: str | None = None,
    ) -> int:
        inserted = 0
        for object_id, payload in rows:
            inserted += int(self._record_version(object_type, object_id, payload, recorded_at=recorded_at))
        self.db.commit()
        return inserted

    def list_versions(self, object_type: str, object_id: str) -> list[dict]:
        rows = self.db.execute(
            """SELECT object_type, object_id, recorded_at, payload_sha256, payload_json
               FROM object_versions
               WHERE object_type=? AND object_id=?
               ORDER BY recorded_at, version_id""",
            (object_type, object_id),
        ).fetchall()
        return [
            {
                "object_type": row["object_type"],
                "object_id": row["object_id"],
                "recorded_at": row["recorded_at"],
                "payload_sha256": row["payload_sha256"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def snapshot_as_of(self, as_of: str, *, object_type: str | None = None, limit: int = 5000) -> list[dict]:
        params: list[object] = [as_of]
        type_filter = ""
        if object_type:
            type_filter = " AND object_type=?"
            params.append(object_type)
        params.append(max(1, min(limit, 10000)))
        rows = self.db.execute(
            f"""SELECT object_type, object_id, recorded_at, payload_sha256, payload_json
                FROM (
                  SELECT object_type, object_id, recorded_at, payload_sha256, payload_json, version_id,
                         ROW_NUMBER() OVER (
                           PARTITION BY object_type, object_id
                           ORDER BY recorded_at DESC, version_id DESC
                         ) AS rn
                  FROM object_versions
                  WHERE recorded_at<=?{type_filter}
                )
                WHERE rn=1
                ORDER BY object_type, object_id
                LIMIT ?""",
            params,
        ).fetchall()
        return [
            {
                "object_type": row["object_type"],
                "object_id": row["object_id"],
                "recorded_at": row["recorded_at"],
                "payload_sha256": row["payload_sha256"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    # --- legacy/raw event layer -------------------------------------------------
    def upsert_events(self, events: list[Event]) -> int:
        for event in events:
            self._record_version("event", event.event_id, event.to_dict(), recorded_at=event.collected_at)
            self.db.execute("""
            INSERT INTO events(event_id, reference_at, source_id, verification_level, country, event_json)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET reference_at=excluded.reference_at, source_id=excluded.source_id,
              verification_level=excluded.verification_level, country=excluded.country, event_json=excluded.event_json,
              updated_at=CURRENT_TIMESTAMP
            """, (event.event_id, event.reference_at, event.source_id, event.verification_level, event.country, json.dumps(event.to_dict(), ensure_ascii=False)))
        self.db.commit()
        return len(events)

    def load_events_since(self, reference_at: str) -> list[Event]:
        rows = self.db.execute(
            "SELECT event_json FROM events WHERE reference_at >= ? ORDER BY reference_at",
            (reference_at,),
        ).fetchall()
        return [Event.from_dict(json.loads(row["event_json"])) for row in rows]

    def load_events_by_ids(self, event_ids: Iterable[str]) -> list[Event]:
        ids = tuple(dict.fromkeys(event_ids))
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.db.execute(f"SELECT event_json FROM events WHERE event_id IN ({placeholders})", ids).fetchall()
        return [Event.from_dict(json.loads(row["event_json"])) for row in rows]

    def list_events(self, *, since: str | None = None, country: str | None = None, limit: int = 200) -> list[dict]:
        sql = "SELECT event_json FROM events WHERE 1=1"
        params: list[object] = []
        if since:
            sql += " AND reference_at >= ?"
            params.append(since)
        if country:
            sql += " AND country = ?"
            params.append(country)
        sql += " ORDER BY reference_at DESC LIMIT ?"
        params.append(max(1, min(limit, 1000)))
        return [json.loads(row["event_json"]) for row in self.db.execute(sql, params).fetchall()]

    # --- v0.4 clusters/reports -------------------------------------------------
    def upsert_clusters(self, clusters: list[EventCluster], generated_at: str) -> int:
        for cluster in clusters:
            payload = {**cluster.to_dict(), "priority_score": score_cluster(cluster), "priority_method_version": "geowatch-priority-v0.4"}
            self.db.execute("""
            INSERT INTO clusters(cluster_id, generated_at, priority_score, cluster_json) VALUES(?,?,?,?)
            ON CONFLICT(cluster_id) DO UPDATE SET generated_at=excluded.generated_at, priority_score=excluded.priority_score,
              cluster_json=excluded.cluster_json, updated_at=CURRENT_TIMESTAMP
            """, (deterministic_cluster_id(cluster), generated_at, score_cluster(cluster), json.dumps(payload, ensure_ascii=False)))
        self.db.commit()
        return len(clusters)

    def upsert_report(self, report: dict, markdown: str) -> str:
        self.db.execute("""
        INSERT INTO reports(report_id, generated_at, report_type, report_json, report_markdown) VALUES(?,?,?,?,?)
        ON CONFLICT(report_id) DO UPDATE SET report_json=excluded.report_json, report_markdown=excluded.report_markdown,
          updated_at=CURRENT_TIMESTAMP
        """, (report["report_id"], report["generated_at"], report["report_type"], json.dumps(report, ensure_ascii=False), markdown))
        self.db.commit()
        return report["report_id"]

    def latest_report(self, report_type: str | None = None) -> dict | None:
        if report_type:
            row = self.db.execute("SELECT report_json FROM reports WHERE report_type=? ORDER BY generated_at DESC LIMIT 1", (report_type,)).fetchone()
        else:
            row = self.db.execute("SELECT report_json FROM reports ORDER BY generated_at DESC LIMIT 1").fetchone()
        return json.loads(row["report_json"]) if row else None

    # --- v0.5 entity/claim/episode layer --------------------------------------
    def upsert_entities(self, entities: Iterable[Entity]) -> int:
        rows = list(entities)
        for entity in rows:
            self._record_version("entity", entity.entity_id, entity.to_dict())
            self.db.execute("""
            INSERT INTO entities(entity_id, entity_type, canonical_name, country, latitude, longitude, entity_json)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(entity_id) DO UPDATE SET entity_type=excluded.entity_type, canonical_name=excluded.canonical_name,
              country=excluded.country, latitude=COALESCE(excluded.latitude, entities.latitude),
              longitude=COALESCE(excluded.longitude, entities.longitude), entity_json=excluded.entity_json,
              updated_at=CURRENT_TIMESTAMP
            """, (
                entity.entity_id, entity.entity_type, entity.canonical_name, entity.country,
                entity.latitude, entity.longitude, json.dumps(entity.to_dict(), ensure_ascii=False),
            ))
        self.db.commit()
        return len(rows)

    def load_entities(self) -> list[Entity]:
        return [Entity.from_dict(json.loads(row["entity_json"])) for row in self.db.execute("SELECT entity_json FROM entities").fetchall()]

    def upsert_relationships(self, relationships: Iterable[Relationship]) -> int:
        rows = list(relationships)
        for relationship in rows:
            self._record_version("relationship", relationship.relationship_id, relationship.to_dict(), recorded_at=relationship.last_seen_at)
            self.db.execute("""
            INSERT INTO relationships(
              relationship_id, source_entity_id, target_entity_id, relationship_type, semantic_class,
              first_seen_at, last_seen_at, valid_from, valid_to, confidence, relationship_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(relationship_id) DO UPDATE SET source_entity_id=excluded.source_entity_id,
              target_entity_id=excluded.target_entity_id, relationship_type=excluded.relationship_type,
              semantic_class=excluded.semantic_class, first_seen_at=excluded.first_seen_at,
              last_seen_at=excluded.last_seen_at, valid_from=excluded.valid_from,
              valid_to=excluded.valid_to, confidence=excluded.confidence, relationship_json=excluded.relationship_json,
              updated_at=CURRENT_TIMESTAMP
            """, (
                relationship.relationship_id, relationship.source_entity_id, relationship.target_entity_id,
                relationship.relationship_type, relationship.semantic_class, relationship.first_seen_at,
                relationship.last_seen_at, relationship.valid_from, relationship.valid_to, relationship.confidence,
                json.dumps(relationship.to_dict(), ensure_ascii=False),
            ))
        self.db.commit()
        return len(rows)

    def load_relationships(self, *, entity_id: str | None = None, relationship_type: str | None = None) -> list[Relationship]:
        sql = "SELECT relationship_json FROM relationships WHERE 1=1"
        params: list[object] = []
        if entity_id:
            sql += " AND (source_entity_id=? OR target_entity_id=?)"
            params.extend([entity_id, entity_id])
        if relationship_type:
            sql += " AND relationship_type=?"
            params.append(relationship_type)
        sql += " ORDER BY last_seen_at DESC"
        return [Relationship.from_dict(json.loads(row["relationship_json"])) for row in self.db.execute(sql, params).fetchall()]

    def upsert_evidence(self, evidence: Iterable[EvidenceRef]) -> int:
        rows = list(evidence)
        for item in rows:
            self._record_version("evidence", item.evidence_id, item.to_dict(), recorded_at=item.observed_at)
            self.db.execute("""
            INSERT INTO evidence(evidence_id, event_id, source_id, verification_level, relation, observed_at, evidence_json)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(evidence_id) DO UPDATE SET relation=excluded.relation, evidence_json=excluded.evidence_json,
              updated_at=CURRENT_TIMESTAMP
            """, (item.evidence_id, item.event_id, item.source_id, item.verification_level, item.relation, item.observed_at, json.dumps(item.to_dict(), ensure_ascii=False)))
        self.db.commit()
        return len(rows)

    def load_evidence(self, *, episode_id: str | None = None) -> list[EvidenceRef]:
        if episode_id:
            rows = self.db.execute("""
              SELECT DISTINCT e.evidence_json FROM evidence e
              JOIN claim_evidence ce ON ce.evidence_id=e.evidence_id
              JOIN claims c ON c.claim_id=ce.claim_id WHERE c.episode_id=?
            """, (episode_id,)).fetchall()
        else:
            rows = self.db.execute("SELECT evidence_json FROM evidence").fetchall()
        return [EvidenceRef.from_dict(json.loads(row["evidence_json"])) for row in rows]

    def upsert_claims(self, claims: Iterable[Claim]) -> int:
        rows = list(claims)
        for claim in rows:
            self._record_version("claim", claim.claim_id, claim.to_dict(), recorded_at=claim.last_seen_at)
            self.db.execute("""
            INSERT INTO claims(claim_id, episode_id, claim_type, topic_key, status, first_seen_at, last_seen_at, claim_json)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(claim_id) DO UPDATE SET episode_id=excluded.episode_id, claim_type=excluded.claim_type,
              topic_key=excluded.topic_key, status=excluded.status, last_seen_at=excluded.last_seen_at,
              claim_json=excluded.claim_json, updated_at=CURRENT_TIMESTAMP
            """, (
                claim.claim_id, claim.episode_id, claim.claim_type, claim.topic_key, claim.status,
                claim.first_seen_at, claim.last_seen_at, json.dumps(claim.to_dict(), ensure_ascii=False),
            ))
            for evidence_id in claim.evidence_ids:
                self.db.execute("INSERT OR IGNORE INTO claim_evidence(claim_id, evidence_id) VALUES(?,?)", (claim.claim_id, evidence_id))
        self.db.commit()
        return len(rows)

    def load_claims(self, *, episode_id: str | None = None) -> list[Claim]:
        if episode_id:
            rows = self.db.execute("SELECT claim_json FROM claims WHERE episode_id=? ORDER BY first_seen_at", (episode_id,)).fetchall()
        else:
            rows = self.db.execute("SELECT claim_json FROM claims ORDER BY first_seen_at").fetchall()
        return [Claim.from_dict(json.loads(row["claim_json"])) for row in rows]

    def upsert_episodes(self, episodes: Iterable[ConflictEpisode]) -> int:
        rows = list(episodes)
        for episode in rows:
            self._record_version("episode", episode.episode_id, episode.to_dict(), recorded_at=episode.last_updated_at)
            strength = episode.evidence_strength.overall_index if episode.evidence_strength else None
            primary_country = episode.countries[0] if episode.countries else None
            self.db.execute("""
            INSERT INTO episodes(episode_id, state, started_at, last_updated_at, primary_country, evidence_strength_index, episode_json)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(episode_id) DO UPDATE SET state=excluded.state, last_updated_at=excluded.last_updated_at,
              primary_country=excluded.primary_country, evidence_strength_index=excluded.evidence_strength_index,
              episode_json=excluded.episode_json, updated_at=CURRENT_TIMESTAMP
            """, (
                episode.episode_id, episode.state, episode.started_at, episode.last_updated_at,
                primary_country, strength, json.dumps(episode.to_dict(), ensure_ascii=False),
            ))
            for event_id in episode.event_ids:
                self.db.execute("INSERT OR IGNORE INTO episode_events(episode_id, event_id) VALUES(?,?)", (episode.episode_id, event_id))
        self.db.commit()
        return len(rows)

    def load_episodes(self, *, since: str | None = None, states: Iterable[str] | None = None, limit: int | None = None) -> list[ConflictEpisode]:
        sql = "SELECT episode_json FROM episodes WHERE 1=1"
        params: list[object] = []
        if since:
            sql += " AND last_updated_at >= ?"
            params.append(since)
        state_values = tuple(states or ())
        if state_values:
            sql += " AND state IN (" + ",".join("?" for _ in state_values) + ")"
            params.extend(state_values)
        sql += " ORDER BY last_updated_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, min(limit, 5000)))
        return [ConflictEpisode.from_dict(json.loads(row["episode_json"])) for row in self.db.execute(sql, params).fetchall()]

    def get_episode(self, episode_id: str) -> ConflictEpisode | None:
        row = self.db.execute("SELECT episode_json FROM episodes WHERE episode_id=?", (episode_id,)).fetchone()
        return ConflictEpisode.from_dict(json.loads(row["episode_json"])) if row else None

    def list_episode_records(
        self,
        *,
        country: str | None = None,
        state: str | None = None,
        since: str | None = None,
        min_strength: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        sql = "SELECT episode_json FROM episodes WHERE 1=1"
        params: list[object] = []
        if country:
            sql += " AND primary_country=?"
            params.append(country)
        if state:
            sql += " AND state=?"
            params.append(state)
        if since:
            sql += " AND last_updated_at>=?"
            params.append(since)
        if min_strength is not None:
            sql += " AND COALESCE(evidence_strength_index,0)>=?"
            params.append(int(min_strength))
        sql += " ORDER BY last_updated_at DESC LIMIT ?"
        params.append(max(1, min(limit, 1000)))
        return [json.loads(row["episode_json"]) for row in self.db.execute(sql, params).fetchall()]

    def record_changes(self, changes: Iterable[dict[str, object]]) -> int:
        rows = list(changes)
        for change in rows:
            self.db.execute(
                "INSERT INTO episode_changes(episode_id, occurred_at, change_type, change_json) VALUES(?,?,?,?)",
                (change["episode_id"], change.get("at") or change.get("occurred_at"), change["change_type"], json.dumps(change, ensure_ascii=False)),
            )
        self.db.commit()
        return len(rows)

    def changes_since(self, since: str, *, limit: int = 500) -> list[dict]:
        rows = self.db.execute(
            "SELECT change_json FROM episode_changes WHERE occurred_at>=? ORDER BY occurred_at LIMIT ?",
            (since, max(1, min(limit, 5000))),
        ).fetchall()
        return [json.loads(row["change_json"]) for row in rows]

    # --- collection audit ------------------------------------------------------
    def get_checkpoint(self, source_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM source_checkpoints WHERE source_id = ?", (source_id,)).fetchone()
        if not row:
            return None
        return {
            "source_id": row["source_id"],
            "last_success_at": row["last_success_at"],
            "last_reference_at": row["last_reference_at"],
            "cursor": json.loads(row["cursor_json"]) if row["cursor_json"] else None,
            "updated_at": row["updated_at"],
        }

    def update_checkpoint(self, source_id: str, *, last_success_at: str, last_reference_at: str | None = None, cursor: dict | None = None) -> None:
        self.db.execute("""
        INSERT INTO source_checkpoints(source_id, last_success_at, last_reference_at, cursor_json)
        VALUES(?,?,?,?)
        ON CONFLICT(source_id) DO UPDATE SET last_success_at=excluded.last_success_at,
          last_reference_at=COALESCE(excluded.last_reference_at, source_checkpoints.last_reference_at),
          cursor_json=excluded.cursor_json, updated_at=CURRENT_TIMESTAMP
        """, (source_id, last_success_at, last_reference_at, json.dumps(cursor, ensure_ascii=False) if cursor is not None else None))
        self.db.commit()

    def record_run(self, *, run_id: str, source_id: str, started_at: str, finished_at: str, status: str, records: int = 0, request: dict | None = None, error: str | None = None) -> None:
        self.db.execute("""
        INSERT INTO collector_runs(run_id, source_id, started_at, finished_at, status, records, request_json, error)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(run_id) DO UPDATE SET finished_at=excluded.finished_at, status=excluded.status,
          records=excluded.records, request_json=excluded.request_json, error=excluded.error,
          updated_at=CURRENT_TIMESTAMP
        """, (run_id, source_id, started_at, finished_at, status, records, json.dumps(request, ensure_ascii=False) if request else None, error))
        self.db.commit()

    def recent_runs(self, *, limit: int = 100) -> list[dict]:
        rows = self.db.execute("SELECT * FROM collector_runs ORDER BY started_at DESC LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
        return [dict(row) for row in rows]

    def add_artifact(self, *, artifact_id: str, source_id: str, sha256: str, collected_at: str, observed_url: str | None, path: str, bytes_count: int) -> None:
        self.db.execute("""
        INSERT OR IGNORE INTO raw_artifacts(artifact_id, source_id, sha256, collected_at, observed_url, path, bytes)
        VALUES(?,?,?,?,?,?,?)
        """, (artifact_id, source_id, sha256, collected_at, observed_url, path, bytes_count))
        self.db.commit()

    # --- alerts ---------------------------------------------------------------
    def enqueue_alert(self, alert: dict[str, object]) -> bool:
        before = self.db.total_changes
        self.db.execute("""
          INSERT OR IGNORE INTO alert_outbox(alert_id, episode_id, created_at, severity, policy_id, payload_json)
          VALUES(?,?,?,?,?,?)
        """, (
            alert["alert_id"], alert["episode_id"], alert["created_at"], alert["severity"],
            alert["policy_id"], json.dumps(alert, ensure_ascii=False),
        ))
        self.db.commit()
        return self.db.total_changes > before

    def pending_alerts(self, *, limit: int = 100) -> list[dict]:
        rows = self.db.execute("SELECT * FROM alert_outbox WHERE status='pending' ORDER BY created_at LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
        return [dict(row) | {"payload": json.loads(row["payload_json"])} for row in rows]

    def mark_alert(self, alert_id: str, *, status: str, error: str | None = None, delivered_at: str | None = None) -> None:
        self.db.execute("""
          UPDATE alert_outbox SET status=?, attempts=attempts+1, last_error=?, delivered_at=COALESCE(?, delivered_at)
          WHERE alert_id=?
        """, (status, error, delivered_at, alert_id))
        self.db.commit()

    def close(self) -> None:
        self.db.close()

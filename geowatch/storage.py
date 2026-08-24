from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .core import EventCluster, deterministic_cluster_id, score_cluster
from .models import Event


class SQLiteStore:
    def __init__(self, path: str | Path = "data/geowatch.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self.db.executescript("""
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
        """)
        self.db.commit()

    def upsert_events(self, events: list[Event]) -> int:
        for event in events:
            self.db.execute("""
            INSERT INTO events(event_id, reference_at, source_id, verification_level, country, event_json)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET reference_at=excluded.reference_at, source_id=excluded.source_id,
              verification_level=excluded.verification_level, country=excluded.country, event_json=excluded.event_json,
              updated_at=CURRENT_TIMESTAMP
            """, (event.event_id, event.reference_at, event.source_id, event.verification_level, event.country, json.dumps(event.to_dict(), ensure_ascii=False)))
        self.db.commit()
        return len(events)

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

    def latest_report(self) -> dict | None:
        row = self.db.execute("SELECT report_json FROM reports ORDER BY generated_at DESC LIMIT 1").fetchone()
        return json.loads(row["report_json"]) if row else None

    def load_events_since(self, reference_at: str) -> list[Event]:
        rows = self.db.execute(
            "SELECT event_json FROM events WHERE reference_at >= ? ORDER BY reference_at",
            (reference_at,),
        ).fetchall()
        return [Event.from_dict(json.loads(row["event_json"])) for row in rows]

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

    def add_artifact(self, *, artifact_id: str, source_id: str, sha256: str, collected_at: str, observed_url: str | None, path: str, bytes_count: int) -> None:
        self.db.execute("""
        INSERT OR IGNORE INTO raw_artifacts(artifact_id, source_id, sha256, collected_at, observed_url, path, bytes)
        VALUES(?,?,?,?,?,?,?)
        """, (artifact_id, source_id, sha256, collected_at, observed_url, path, bytes_count))
        self.db.commit()

    def close(self) -> None:
        self.db.close()

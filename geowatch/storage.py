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
            payload = {**cluster.to_dict(), "priority_score": score_cluster(cluster), "priority_method_version": "geowatch-priority-v0.3"}
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

    def close(self) -> None:
        self.db.close()

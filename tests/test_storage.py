from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geowatch.core import cluster_events
from geowatch.models import Event
from geowatch.reports import build_report, render_markdown
from geowatch.storage import SQLiteStore


class StorageTests(unittest.TestCase):
    def test_round_trip_latest_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event = Event(
                event_id="x", source_id="fixture", source_kind="news", title="Port blockade reported",
                event_type="media_report", reference_at="2026-08-24T10:00:00+00:00",
                collected_at="2026-08-24T10:05:00+00:00", verification_level="osint_signal",
                source_url="https://example.com/x", publisher="example.com", impact_areas=("shipping", "trade")
            )
            report = build_report(cluster_events([event]), generated_at="2026-08-24T11:00:00+00:00")
            store = SQLiteStore(Path(tmp) / "db.sqlite")
            store.upsert_events([event])
            store.upsert_clusters(cluster_events([event]), report["generated_at"])
            store.upsert_report(report, render_markdown(report))
            loaded = store.latest_report()
            store.close()
            self.assertEqual(loaded["report_id"], report["report_id"])


if __name__ == "__main__":
    unittest.main()

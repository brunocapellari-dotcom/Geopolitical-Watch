from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from geowatch.core import cluster_events
from geowatch.evaluation import replay_fixture
from geowatch.geo import normalize_country
from geowatch.history import iter_windows, overlap_start
from geowatch.http import HttpResponse
from geowatch.models import Event
from geowatch.quality import load_profiles
from geowatch.sources import gdelt, ucdp
from geowatch.storage import SQLiteStore


class V04HistoryQualityTests(unittest.TestCase):
    def event(self, event_id: str, *, at: str, country: str, lat: float, lon: float) -> Event:
        return Event(event_id=event_id, source_id="gdelt_conflict_news", source_kind="news", title="Missile strike disrupts port operations", event_type="media_report", reference_at=at, collected_at="2026-08-25T01:00:00+00:00", verification_level="osint_signal", country=country, latitude=lat, longitude=lon, source_url=f"https://{event_id}.example/x", publisher=f"{event_id}.example")

    def test_country_aliases_and_cross_midnight_clustering(self) -> None:
        self.assertEqual(normalize_country("Russian Federation"), "Russia")
        a = self.event("a", at="2026-08-24T23:30:00+00:00", country="Ukraine", lat=50.0, lon=30.0)
        b = self.event("b", at="2026-08-25T00:15:00+00:00", country="Ukraine", lat=50.05, lon=30.05)
        self.assertEqual(len(cluster_events([a, b])), 1)

    def test_country_and_distance_prevent_bad_clusters(self) -> None:
        a = self.event("a", at="2026-08-24T10:00:00+00:00", country="Ukraine", lat=46.48, lon=30.73)
        other_country = self.event("b", at="2026-08-24T10:05:00+00:00", country="Russian Federation", lat=46.50, lon=30.75)
        far = self.event("c", at="2026-08-24T10:05:00+00:00", country="Ukraine", lat=49.84, lon=24.03)
        self.assertEqual(len(cluster_events([a, other_country])), 2)
        self.assertEqual(len(cluster_events([a, far], max_distance_km=250)), 2)

    def test_windows_and_checkpoint_overlap(self) -> None:
        windows = list(iter_windows("2026-08-24T00:00:00Z", "2026-08-25T00:00:00Z", hours=6))
        self.assertEqual(len(windows), 4)
        start = overlap_start("2026-08-24T10:00:00+00:00", overlap_minutes=30, now=datetime(2026, 8, 24, 12, tzinfo=timezone.utc))
        self.assertEqual(start.isoformat(), "2026-08-24T09:30:00+00:00")

    def test_checkpoint_and_recent_event_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "db.sqlite")
            store.update_checkpoint("gdelt_conflict_news", last_success_at="2026-08-24T10:00:00+00:00", last_reference_at="2026-08-24T09:55:00+00:00", cursor={"page": 1})
            checkpoint = store.get_checkpoint("gdelt_conflict_news")
            self.assertEqual(checkpoint["cursor"], {"page": 1})
            event = self.event("x", at="2026-08-24T09:55:00+00:00", country="Ukraine", lat=50.0, lon=30.0)
            store.upsert_events([event])
            loaded = store.load_events_since("2026-08-24T09:00:00+00:00")
            store.close()
            self.assertEqual([row.event_id for row in loaded], ["x"])

    def test_gdelt_precise_history_window_uses_start_end(self) -> None:
        captured = {}
        def fake_get(url, **kwargs):
            captured.update(kwargs["query"])
            return HttpResponse(b'{"articles": []}', url, "application/json")
        with patch("geowatch.sources.gdelt.get", fake_get):
            gdelt.collect(start_datetime="20260824000000", end_datetime="20260824060000")
        self.assertEqual(captured["startdatetime"], "20260824000000")
        self.assertEqual(captured["enddatetime"], "20260824060000")
        self.assertNotIn("timespan", captured)

    def test_ucdp_history_filters_are_forwarded_with_token_header(self) -> None:
        calls = []
        def fake_get(url, **kwargs):
            calls.append(kwargs)
            return HttpResponse(json.dumps({"TotalPages": 1, "Result": []}).encode(), url, "application/json")
        with patch("geowatch.sources.ucdp.get", fake_get):
            ucdp.collect_all(token="secret", start_date="2026-08-01", end_date="2026-08-24")
        self.assertEqual(calls[0]["headers"]["x-ucdp-access-token"], "secret")
        self.assertEqual(calls[0]["query"]["StartDate"], "2026-08-01")
        self.assertEqual(calls[0]["query"]["EndDate"], "2026-08-24")

    def test_source_profiles_are_descriptive_not_media_reputation_scores(self) -> None:
        profiles = load_profiles("config/source_quality.json")
        profile = profiles["gdelt_conflict_news"]
        self.assertEqual(profile.governance_class, "news_aggregator")
        self.assertFalse(profile.official_or_primary)
        self.assertFalse(hasattr(profile, "reliability_score"))

    def test_replay_fixture_has_perfect_pairwise_result(self) -> None:
        result = replay_fixture("tests/fixtures/clustering_eval.json")
        self.assertEqual(result["pairwise_precision"], 1.0)
        self.assertEqual(result["pairwise_recall"], 1.0)
        self.assertEqual(result["false_positive_pairs"], [])
        self.assertEqual(result["missed_pairs"], [])


if __name__ == "__main__":
    unittest.main()

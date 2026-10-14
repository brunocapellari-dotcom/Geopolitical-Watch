from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from geowatch.http import HttpResponse
from geowatch.pipeline import _collect_incremental


class GdeltBoundedWindowTests(unittest.TestCase):
    def test_stale_checkpoint_is_bounded_to_configured_lookback(self) -> None:
        now = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
        spec = {
            "source_id": "gdelt_conflict_news",
            "kind": "gdelt",
            "lookback_hours": 12,
            "maxrecords": 100,
            "query": "conflict",
        }
        request_meta: dict[str, object] = {}
        with patch(
            "geowatch.pipeline.gdelt.collect",
            return_value=(b'{"articles":[]}', "https://api.gdeltproject.org/test"),
        ) as mocked:
            _collect_incremental(
                spec,
                checkpoint={"last_success_at": "2026-10-09T15:00:00+00:00"},
                now=now,
                default_lookback_hours=12,
                overlap_minutes=120,
                request_meta=request_meta,
            )
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["start_datetime"], "20261012060000")
        self.assertEqual(kwargs["end_datetime"], "20261012180000")
        self.assertEqual(kwargs["maxrecords"], 100)
        self.assertTrue(request_meta["window_bounded"])

    def test_recent_checkpoint_keeps_overlap_without_expanding_to_full_lookback(self) -> None:
        now = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
        spec = {"source_id": "gdelt_conflict_news", "kind": "gdelt", "lookback_hours": 12, "maxrecords": 100}
        request_meta: dict[str, object] = {}
        with patch(
            "geowatch.pipeline.gdelt.collect",
            return_value=(b'{"articles":[]}', "https://api.gdeltproject.org/test"),
        ) as mocked:
            _collect_incremental(
                spec,
                checkpoint={"last_success_at": "2026-10-12T17:00:00+00:00"},
                now=now,
                default_lookback_hours=12,
                overlap_minutes=120,
                request_meta=request_meta,
            )
        self.assertEqual(mocked.call_args.kwargs["start_datetime"], "20261012150000")
        self.assertFalse(request_meta["window_bounded"])


if __name__ == "__main__":
    unittest.main()

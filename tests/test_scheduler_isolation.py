from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from geowatch.collector_scheduler import (
    _isolated_analysis_result,
    _isolated_sanctions_result,
    _isolated_source_result,
)


class SchedulerIsolationTests(unittest.TestCase):
    def test_source_child_success_is_parsed(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python"], returncode=0,
            stdout=json.dumps({"source_id": "gdelt_conflict_news", "status": "ok", "records": 3}),
            stderr="",
        )
        with patch("geowatch.collector_scheduler.subprocess.run", return_value=completed):
            result = _isolated_source_result("gdelt_conflict_news")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["records"], 3)
        self.assertTrue(result["isolated"])

    def test_source_timeout_is_bounded_and_recorded(self) -> None:
        with patch(
            "geowatch.collector_scheduler.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=75),
        ), patch("geowatch.collector_scheduler._record_parent_failure") as record:
            result = _isolated_source_result("gdelt_conflict_news")
        self.assertEqual(result["status"], "error")
        self.assertIn("timeout", result["error"])
        self.assertTrue(result["isolated"])
        record.assert_called_once()

    def test_nonzero_source_child_is_recorded_as_error(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python"], returncode=2, stdout="", stderr="provider failed",
        )
        with patch("geowatch.collector_scheduler.subprocess.run", return_value=completed), \
             patch("geowatch.collector_scheduler._record_parent_failure") as record:
            result = _isolated_source_result("celestrak")
        self.assertEqual(result["status"], "error")
        self.assertIn("exited 2", result["error"])
        record.assert_called_once()

    def test_sanctions_child_success_is_parsed(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python"], returncode=0,
            stdout=json.dumps({"generated_at": "2026-10-12T00:00:00Z", "results": {
                "unsc_sanctions": {"status": "ok", "records": 10},
                "uk_sanctions": {"status": "ok", "records": 20},
            }}),
            stderr="",
        )
        with patch("geowatch.collector_scheduler.subprocess.run", return_value=completed):
            result = _isolated_sanctions_result()
        self.assertTrue(result["isolated"])
        self.assertEqual(result["results"]["uk_sanctions"]["records"], 20)

    def test_sanctions_child_failure_isolated_from_server(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python"], returncode=-9, stdout="", stderr="",
        )
        with patch("geowatch.collector_scheduler.subprocess.run", return_value=completed), \
             patch("geowatch.collector_scheduler._record_parent_failure") as record:
            result = _isolated_sanctions_result()
        self.assertEqual(result["status"], "error")
        self.assertEqual(record.call_count, 2)

    def test_analysis_child_success_is_parsed(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python"], returncode=0,
            stdout=json.dumps({"generated_at": "2026-10-12T00:00:00Z", "episodes": 1}),
            stderr="",
        )
        with patch("geowatch.collector_scheduler.subprocess.run", return_value=completed):
            result = _isolated_analysis_result()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["episodes"], 1)
        self.assertTrue(result["isolated"])

    def test_analysis_timeout_fails_closed(self) -> None:
        with patch(
            "geowatch.collector_scheduler.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=180),
        ):
            result = _isolated_analysis_result()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "TimeoutExpired")
        self.assertTrue(result["isolated"])


if __name__ == "__main__":
    unittest.main()

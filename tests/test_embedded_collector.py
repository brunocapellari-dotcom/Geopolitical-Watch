from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from geowatch.embedded_collector import config_path, enabled, interval_seconds, reset_for_tests, run_once, status


class EmbeddedCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_for_tests()

    def tearDown(self) -> None:
        reset_for_tests()

    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(enabled())
            self.assertFalse(status()["enabled"])
            self.assertEqual(config_path(), "config/sources.public-beta.json")

    def test_replit_deployment_uses_production_profile(self) -> None:
        with patch.dict(os.environ, {"REPLIT_DEPLOYMENT": "1"}, clear=True):
            self.assertEqual(config_path(), "config/sources.production.json")

    def test_explicit_config_overrides_runtime_default(self) -> None:
        env = {"REPLIT_DEPLOYMENT": "1", "GEOWATCH_COLLECT_CONFIG": "config/custom.json"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(config_path(), "config/custom.json")

    def test_interval_is_bounded(self) -> None:
        with patch.dict(os.environ, {"GEOWATCH_COLLECT_INTERVAL_SECONDS": "10"}, clear=True):
            self.assertEqual(interval_seconds(), 900)
        with patch.dict(os.environ, {"GEOWATCH_COLLECT_INTERVAL_SECONDS": "999999"}, clear=True):
            self.assertEqual(interval_seconds(), 86400)

    def test_run_once_records_success_without_overlapping_thread(self) -> None:
        result_payload = {"generated_at": "2026-09-14T12:00:00+00:00", "source_results": []}
        with patch("geowatch.embedded_collector.run", return_value=result_payload) as mocked:
            result = run_once()
        self.assertEqual(result["status"], "ok")
        state = status()
        self.assertEqual(state["last_status"], "ok")
        self.assertEqual(state["run_count"], 1)
        mocked.assert_called_once()

    def test_run_once_records_failure_without_crashing_server(self) -> None:
        with patch("geowatch.embedded_collector.run", side_effect=RuntimeError("provider down")):
            result = run_once()
        self.assertEqual(result["status"], "error")
        self.assertIn("RuntimeError", status()["last_error"])


if __name__ == "__main__":
    unittest.main()

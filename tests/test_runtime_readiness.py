from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from geowatch.runtime_readiness import build_runtime_readiness


class RuntimeReadinessTests(unittest.TestCase):
    def test_default_runtime_is_not_claimed_ready(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = build_runtime_readiness()
        self.assertFalse(result["private_web_ready"])
        self.assertFalse(result["continuous_ais_ready"])
        self.assertTrue(result["blockers"])

    def test_configured_persistent_runtime_is_private_web_ready(self) -> None:
        env = {
            "GEOWATCH_API_TOKEN": "secret",
            "GEOWATCH_DB_URL": "postgresql://user:pass@host/db",
            "GEOWATCH_RAW_BACKEND": "postgres",
            "GEOWATCH_EMBEDDED_COLLECTOR": "1",
            "GEOWATCH_WPI_RUNTIME": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            result = build_runtime_readiness()
        self.assertTrue(result["private_web_ready"])
        self.assertTrue(result["live_aircraft_ready"])
        self.assertFalse(result["continuous_ais_ready"])
        self.assertEqual(result["raw_backend"], "postgresql-compressed")

    def test_continuous_ais_requires_key_and_always_on_compute(self) -> None:
        env = {
            "GEOWATCH_API_TOKEN": "secret",
            "GEOWATCH_DB_URL": "postgresql://user:pass@host/db",
            "GEOWATCH_RAW_BACKEND": "postgres",
            "GEOWATCH_EMBEDDED_COLLECTOR": "1",
            "GEOWATCH_WPI_RUNTIME": "1",
            "AISSTREAM_API_KEY": "not-a-real-key",
            "GEOWATCH_ALWAYS_ON": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            result = build_runtime_readiness()
        self.assertTrue(result["continuous_ais_ready"])


if __name__ == "__main__":
    unittest.main()

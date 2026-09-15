from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from geowatch.runtime_guard import production_requirements, strict_production_mode, validate_production_runtime
from geowatch.storage_factory import backend_name, configured_database_url


class ReplitRuntimeTests(unittest.TestCase):
    def test_replit_database_url_selects_postgres(self) -> None:
        env = {"DATABASE_URL": "postgresql://user:secret@example.invalid/replit"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(configured_database_url(), env["DATABASE_URL"])
            self.assertEqual(backend_name(), "postgresql-postgis")

    def test_published_replit_is_strict_automatically(self) -> None:
        with patch.dict(os.environ, {"REPLIT_DEPLOYMENT": "1"}, clear=True):
            self.assertTrue(strict_production_mode())
            with self.assertRaises(RuntimeError):
                validate_production_runtime()

    def test_strict_mode_rejects_short_secret_and_ephemeral_state(self) -> None:
        env = {
            "GEOWATCH_STRICT_PRODUCTION": "1",
            "GEOWATCH_API_TOKEN": "short",
            "GEOWATCH_COOKIE_SECURE": "0",
        }
        with patch.dict(os.environ, env, clear=True):
            checks = production_requirements()
            self.assertFalse(checks["private_auth_secret"])
            self.assertFalse(checks["persistent_database"])
            self.assertFalse(checks["persistent_raw_evidence"])
            self.assertFalse(checks["embedded_collector"])
            self.assertFalse(checks["secure_cookie"])
            with self.assertRaises(RuntimeError):
                validate_production_runtime()

    def test_strict_mode_accepts_complete_replit_configuration(self) -> None:
        env = {
            "REPLIT_DEPLOYMENT": "1",
            "DATABASE_URL": "postgresql://user:secret@example.invalid/replit",
            "GEOWATCH_API_TOKEN": "a-secure-private-secret-value",
            "GEOWATCH_RAW_BACKEND": "postgres",
            "GEOWATCH_EMBEDDED_COLLECTOR": "1",
            "GEOWATCH_COOKIE_SECURE": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            checks = validate_production_runtime()
        self.assertTrue(all(checks.values()))


if __name__ == "__main__":
    unittest.main()

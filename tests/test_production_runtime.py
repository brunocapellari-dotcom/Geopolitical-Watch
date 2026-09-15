from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from geowatch.runtime_guard import production_requirements, strict_production_mode, validate_production_runtime
from geowatch.storage_factory import backend_name, configured_database_url


class ProductionRuntimeTests(unittest.TestCase):
    def test_legacy_database_url_remains_postgres_compatibility_fallback(self) -> None:
        env = {"DATABASE_URL": "postgresql://user:secret@example.invalid/geowatch"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(configured_database_url(), env["DATABASE_URL"])
            self.assertEqual(backend_name(), "postgresql-postgis")

    def test_explicit_production_mode_is_strict(self) -> None:
        with patch.dict(os.environ, {"GEOWATCH_STRICT_PRODUCTION": "1"}, clear=True):
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
            self.assertFalse(checks["collection_path_configured"])
            self.assertTrue(checks["duplicate_collectors_disabled"])
            self.assertFalse(checks["secure_cookie"])
            with self.assertRaises(RuntimeError):
                validate_production_runtime()

    def test_strict_mode_accepts_complete_generic_configuration(self) -> None:
        env = {
            "GEOWATCH_STRICT_PRODUCTION": "1",
            "GEOWATCH_DB_URL": "postgresql://user:secret@example.invalid/geowatch",
            "GEOWATCH_API_TOKEN": "a" * 40,
            "GEOWATCH_RAW_BACKEND": "postgres",
            "GEOWATCH_EXTERNAL_SCHEDULER": "1",
            "GEOWATCH_COOKIE_SECURE": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            checks = validate_production_runtime()
        self.assertTrue(all(checks.values()))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from geowatch.runtime_guard import production_requirements


class CollectionModeGuardTests(unittest.TestCase):
    def test_exactly_one_collection_mode_is_required(self) -> None:
        base = {
            "GEOWATCH_API_TOKEN": "x" * 40,
            "GEOWATCH_RAW_BACKEND": "postgres",
            "GEOWATCH_DB_URL": "postgresql://user:pass@example.invalid/db",
            "GEOWATCH_COOKIE_SECURE": "1",
        }
        with patch.dict(os.environ, {**base, "GEOWATCH_EMBEDDED_COLLECTOR": "1", "GEOWATCH_SOURCE_SCHEDULER": "1"}, clear=True), \
             patch("geowatch.runtime_guard.backend_name", return_value="postgresql-postgis"), \
             patch("geowatch.runtime_guard.raw_backend_name", return_value="postgresql-compressed"):
            checks = production_requirements()
            self.assertFalse(checks["collection_path_configured"])
            self.assertFalse(checks["duplicate_collectors_disabled"])

        with patch.dict(os.environ, {**base, "GEOWATCH_SOURCE_SCHEDULER": "1"}, clear=True), \
             patch("geowatch.runtime_guard.backend_name", return_value="postgresql-postgis"), \
             patch("geowatch.runtime_guard.raw_backend_name", return_value="postgresql-compressed"):
            checks = production_requirements()
            self.assertTrue(checks["collection_path_configured"])
            self.assertTrue(checks["duplicate_collectors_disabled"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from geowatch.storage_factory import backend_name, configured_database_url


class CloudSqlRuntimeTests(unittest.TestCase):
    def test_split_cloud_sql_settings_build_postgres_url_without_losing_special_password_chars(self) -> None:
        env = {
            "GEOWATCH_DB_USER": "geowatch",
            "GEOWATCH_DB_PASSWORD": "a/b:c@d?e#f",
            "GEOWATCH_DB_NAME": "geowatch",
            "GEOWATCH_DB_HOST": "/cloudsql/example:region:instance",
        }
        with patch.dict(os.environ, env, clear=True):
            url = configured_database_url()
            name = backend_name()
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith("postgresql://geowatch:"))
        self.assertIn("a%2Fb%3Ac%40d%3Fe%23f", url)
        self.assertIn("host=%2Fcloudsql%2Fexample%3Aregion%3Ainstance", url)
        self.assertEqual(name, "postgresql-postgis")

    def test_partial_split_cloud_sql_settings_fail_closed(self) -> None:
        with patch.dict(os.environ, {"GEOWATCH_DB_USER": "geowatch"}, clear=True):
            with self.assertRaises(RuntimeError):
                configured_database_url()

    def test_direct_database_url_keeps_priority(self) -> None:
        env = {
            "GEOWATCH_DB_URL": "postgresql://direct/db",
            "GEOWATCH_DB_USER": "ignored",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(configured_database_url(), "postgresql://direct/db")


if __name__ == "__main__":
    unittest.main()

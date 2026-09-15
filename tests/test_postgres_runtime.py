from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from geowatch.storage_postgres import PostgresStore
from geowatch.storage_postgres_runtime import RuntimePostgresStore, reset_schema_cache_for_tests


class PostgresRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_schema_cache_for_tests()

    def tearDown(self) -> None:
        reset_schema_cache_for_tests()

    def test_schema_init_runs_once_for_same_runtime_key(self) -> None:
        store = object.__new__(RuntimePostgresStore)
        store._runtime_schema_key = "same-db"
        with patch.object(PostgresStore, "_init", autospec=True) as base_init:
            store._init(Path("sql/postgres_postgis.sql"))
            store._init(Path("sql/postgres_postgis.sql"))
        self.assertEqual(base_init.call_count, 1)

    def test_failed_schema_init_is_not_cached(self) -> None:
        store = object.__new__(RuntimePostgresStore)
        store._runtime_schema_key = "failing-db"
        with patch.object(PostgresStore, "_init", side_effect=[RuntimeError("db down"), None]) as base_init:
            with self.assertRaises(RuntimeError):
                store._init(Path("sql/postgres_postgis.sql"))
            store._init(Path("sql/postgres_postgis.sql"))
        self.assertEqual(base_init.call_count, 2)


if __name__ == "__main__":
    unittest.main()

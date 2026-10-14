from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geowatch.raw_store import (
    LocalRawStore,
    PostgresRawStore,
    S3RawStore,
    open_raw_store,
    raw_backend_name,
    reset_raw_schema_cache_for_tests,
)


class _Cursor:
    def __init__(self) -> None:
        self.execute_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *_args, **_kwargs) -> None:
        self.execute_count += 1


class _DB:
    def __init__(self) -> None:
        self.cursor_obj = _Cursor()
        self.commit_count = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self) -> None:
        self.commit_count += 1


class RuntimeRawStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_raw_schema_cache_for_tests()

    def tearDown(self) -> None:
        reset_raw_schema_cache_for_tests()

    def test_local_store_remains_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            store = open_raw_store(tmp)
            self.assertIsInstance(store, LocalRawStore)
            ref, digest = store.put("source", "2026-09-14T10:00:00Z", b"payload", "json")
            self.assertTrue(Path(ref).exists())
            self.assertEqual(len(digest), 64)
            self.assertEqual(raw_backend_name(tmp), "filesystem")

    def test_postgres_backend_requires_dsn(self) -> None:
        with patch.dict(os.environ, {"GEOWATCH_RAW_BACKEND": "postgres"}, clear=True):
            with self.assertRaises(RuntimeError):
                open_raw_store()

    def test_postgres_backend_selection_is_lazy(self) -> None:
        env = {
            "GEOWATCH_RAW_BACKEND": "postgres",
            "GEOWATCH_DB_URL": "postgresql://user:secret@example.invalid/db",
        }
        with patch.dict(os.environ, env, clear=True):
            store = open_raw_store()
            self.assertIsInstance(store, PostgresRawStore)
            self.assertEqual(raw_backend_name(), "postgresql-compressed")

    def test_s3_backend_requires_bucket(self) -> None:
        with patch.dict(os.environ, {"GEOWATCH_RAW_BACKEND": "s3"}, clear=True):
            with self.assertRaises(RuntimeError):
                open_raw_store()

    def test_s3_backend_selection_is_lazy(self) -> None:
        env = {
            "GEOWATCH_RAW_BACKEND": "neon-object-storage",
            "GEOWATCH_RAW_S3_BUCKET": "geowatch-raw",
            "AWS_ENDPOINT_URL_S3": "https://example.invalid",
            "AWS_REGION": "us-east-1",
        }
        with patch.dict(os.environ, env, clear=True), patch("geowatch.raw_store.S3RawStore", autospec=True) as mocked:
            open_raw_store()
            mocked.assert_called_once_with("geowatch-raw", "raw")
            self.assertEqual(raw_backend_name(), "s3-compatible")

    def test_legacy_database_url_fallback_is_supported(self) -> None:
        env = {
            "GEOWATCH_RAW_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:secret@example.invalid/legacy",
        }
        with patch.dict(os.environ, env, clear=True):
            store = open_raw_store()
            self.assertIsInstance(store, PostgresRawStore)
            self.assertEqual(store.dsn, env["DATABASE_URL"])

    def test_raw_schema_init_runs_once_per_dsn(self) -> None:
        store = PostgresRawStore("postgresql://user:secret@example.invalid/db")
        db = _DB()
        store._ensure_table(db)
        first_execute_count = db.cursor_obj.execute_count
        first_commit_count = db.commit_count
        store._ensure_table(db)
        # Four canonical DDL statements are executed during the single initialization.
        # A second ensure on the same DSN must execute no additional SQL or commit.
        self.assertEqual(first_execute_count, 4)
        self.assertEqual(db.cursor_obj.execute_count, first_execute_count)
        self.assertEqual(first_commit_count, 1)
        self.assertEqual(db.commit_count, first_commit_count)


if __name__ == "__main__":
    unittest.main()

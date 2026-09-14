from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geowatch.raw_store import LocalRawStore, PostgresRawStore, open_raw_store, raw_backend_name


class RuntimeRawStoreTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from .storage_postgres import PostgresStore

_SCHEMA_LOCK = threading.Lock()
_SCHEMA_READY: set[str] = set()


def _schema_key(dsn: str) -> str:
    return hashlib.sha256(dsn.encode("utf-8")).hexdigest()


class RuntimePostgresStore(PostgresStore):
    """PostgresStore that runs idempotent schema DDL once per process/DSN.

    A new deployment or process restart starts with an empty cache and therefore
    executes the canonical schema again. Normal request-scoped connections skip
    repeated CREATE EXTENSION/TABLE/INDEX work after the first successful init.
    """

    def __init__(self, dsn: str, schema_path: str | Path = "sql/postgres_postgis.sql") -> None:
        self._runtime_schema_key = _schema_key(dsn)
        super().__init__(dsn, schema_path=schema_path)

    def _init(self, schema_path: Path) -> None:
        key = self._runtime_schema_key
        if key in _SCHEMA_READY:
            return
        with _SCHEMA_LOCK:
            if key in _SCHEMA_READY:
                return
            super()._init(schema_path)
            _SCHEMA_READY.add(key)


def reset_schema_cache_for_tests() -> None:
    with _SCHEMA_LOCK:
        _SCHEMA_READY.clear()

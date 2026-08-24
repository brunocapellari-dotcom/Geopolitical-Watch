from __future__ import annotations

import os
from pathlib import Path

from .storage import SQLiteStore


def open_store(location: str | Path | None = None):
    """Open the configured storage backend.

    Precedence: explicit argument -> GEOWATCH_DB_URL -> GEOWATCH_DB -> SQLite default.
    PostgreSQL is activated only for postgresql:// or postgres:// DSNs.
    """
    value = str(location) if location is not None else os.environ.get("GEOWATCH_DB_URL") or os.environ.get("GEOWATCH_DB") or "data/geowatch.db"
    if value.startswith(("postgresql://", "postgres://")):
        from .storage_postgres import PostgresStore
        return PostgresStore(value)
    return SQLiteStore(value)


def backend_name(location: str | Path | None = None) -> str:
    value = str(location) if location is not None else os.environ.get("GEOWATCH_DB_URL") or os.environ.get("GEOWATCH_DB") or "data/geowatch.db"
    return "postgresql-postgis" if value.startswith(("postgresql://", "postgres://")) else "sqlite"

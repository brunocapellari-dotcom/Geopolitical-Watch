from __future__ import annotations

import os
from pathlib import Path

from .storage import SQLiteStore


def configured_database_url() -> str | None:
    """Return the configured PostgreSQL URL, including Replit's DATABASE_URL."""
    value = os.environ.get("GEOWATCH_DB_URL") or os.environ.get("DATABASE_URL")
    value = value.strip() if value else ""
    return value or None


def _location(location: str | Path | None = None) -> str:
    if location is not None:
        return str(location)
    return configured_database_url() or os.environ.get("GEOWATCH_DB") or "data/geowatch.db"


def open_store(location: str | Path | None = None):
    """Open the configured storage backend.

    Precedence: explicit argument -> GEOWATCH_DB_URL -> DATABASE_URL (Replit)
    -> GEOWATCH_DB -> SQLite default. PostgreSQL is activated only for
    postgresql:// or postgres:// DSNs.
    """
    value = _location(location)
    if value.startswith(("postgresql://", "postgres://")):
        from .storage_postgres import PostgresStore
        return PostgresStore(value)
    return SQLiteStore(value)


def backend_name(location: str | Path | None = None) -> str:
    value = _location(location)
    return "postgresql-postgis" if value.startswith(("postgresql://", "postgres://")) else "sqlite"

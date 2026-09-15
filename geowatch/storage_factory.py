from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

from .storage import SQLiteStore

_CLOUD_SQL_KEYS = (
    "GEOWATCH_DB_USER",
    "GEOWATCH_DB_PASSWORD",
    "GEOWATCH_DB_NAME",
    "GEOWATCH_DB_HOST",
)


def _split_database_url() -> str | None:
    values = {name: os.environ.get(name, "").strip() for name in _CLOUD_SQL_KEYS}
    present = {name for name, value in values.items() if value}
    if not present:
        return None
    missing = [name for name in _CLOUD_SQL_KEYS if not values[name]]
    if missing:
        raise RuntimeError("incomplete split database configuration: " + ", ".join(missing))
    user = quote(values["GEOWATCH_DB_USER"], safe="")
    password = quote(values["GEOWATCH_DB_PASSWORD"], safe="")
    database = quote(values["GEOWATCH_DB_NAME"], safe="")
    host = quote(values["GEOWATCH_DB_HOST"], safe="")
    return f"postgresql://{user}:{password}@/{database}?host={host}"


def configured_database_url() -> str | None:
    """Return the configured PostgreSQL URL.

    Direct ``GEOWATCH_DB_URL`` remains the highest-priority explicit contract.
    Cloud Run may instead supply split settings so only the password is secret.
    ``DATABASE_URL`` remains a compatibility fallback for older deployments.
    """
    value = os.environ.get("GEOWATCH_DB_URL")
    value = value.strip() if value else ""
    if value:
        return value
    split = _split_database_url()
    if split:
        return split
    legacy = os.environ.get("DATABASE_URL")
    legacy = legacy.strip() if legacy else ""
    return legacy or None


def _location(location: str | Path | None = None) -> str:
    if location is not None:
        return str(location)
    return configured_database_url() or os.environ.get("GEOWATCH_DB") or "data/geowatch.db"


def open_store(location: str | Path | None = None):
    """Open SQLite for local/test use or PostgreSQL/PostGIS for production."""
    value = _location(location)
    if value.startswith(("postgresql://", "postgres://")):
        from .storage_postgres_runtime import RuntimePostgresStore

        return RuntimePostgresStore(value)
    return SQLiteStore(value)


def backend_name(location: str | Path | None = None) -> str:
    value = _location(location)
    return "postgresql-postgis" if value.startswith(("postgresql://", "postgres://")) else "sqlite"

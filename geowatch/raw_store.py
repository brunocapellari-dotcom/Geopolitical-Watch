from __future__ import annotations

import hashlib
import os
import threading
import zlib
from pathlib import Path

_RAW_SCHEMA_LOCK = threading.Lock()
_RAW_SCHEMA_READY: set[str] = set()


class LocalRawStore:
    def __init__(self, root: str | Path = "data/raw") -> None:
        self.root = Path(root)

    def put(self, source_id: str, collected_at: str, payload: bytes, extension: str) -> tuple[str, str]:
        digest = hashlib.sha256(payload).hexdigest()
        path = self.root / source_id / collected_at[:10] / f"{digest}.{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(payload)
        return str(path), digest


class PostgresRawStore:
    """Compressed raw payload store sharing the structured PostgreSQL database."""

    def __init__(self, dsn: str) -> None:
        if not dsn.startswith(("postgresql://", "postgres://")):
            raise ValueError("PostgresRawStore requires a PostgreSQL DSN")
        self.dsn = dsn
        self._schema_key = hashlib.sha256(dsn.encode("utf-8")).hexdigest()

    def _ensure_table(self, db) -> None:
        if self._schema_key in _RAW_SCHEMA_READY:
            return
        with _RAW_SCHEMA_LOCK:
            if self._schema_key in _RAW_SCHEMA_READY:
                return
            with db.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS raw_payloads (
                        source_id TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        collected_at TIMESTAMPTZ NOT NULL,
                        extension TEXT NOT NULL,
                        compression TEXT NOT NULL DEFAULT 'zlib',
                        original_bytes BIGINT NOT NULL,
                        stored_bytes BIGINT NOT NULL,
                        payload BYTEA NOT NULL,
                        PRIMARY KEY(source_id, sha256)
                    )
                """)
            db.commit()
            _RAW_SCHEMA_READY.add(self._schema_key)

    def put(self, source_id: str, collected_at: str, payload: bytes, extension: str) -> tuple[str, str]:
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PostgreSQL RAW backend requires psycopg") from exc
        digest = hashlib.sha256(payload).hexdigest()
        compressed = zlib.compress(payload, level=6)
        with psycopg.connect(self.dsn) as db:
            self._ensure_table(db)
            with db.cursor() as cur:
                cur.execute("""
                    INSERT INTO raw_payloads(
                        source_id, sha256, collected_at, extension, compression,
                        original_bytes, stored_bytes, payload
                    ) VALUES(%s,%s,%s,%s,'zlib',%s,%s,%s)
                    ON CONFLICT(source_id, sha256) DO NOTHING
                """, (
                    source_id, digest, collected_at, extension,
                    len(payload), len(compressed), compressed,
                ))
            db.commit()
        ref = f"pgraw://{source_id}/{collected_at[:10]}/{digest}.{extension}"
        return ref, digest

    def get(self, source_id: str, digest: str) -> bytes | None:
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PostgreSQL RAW backend requires psycopg") from exc
        with psycopg.connect(self.dsn) as db:
            self._ensure_table(db)
            with db.cursor() as cur:
                cur.execute(
                    "SELECT compression, payload FROM raw_payloads WHERE source_id=%s AND sha256=%s",
                    (source_id, digest),
                )
                row = cur.fetchone()
        if not row:
            return None
        compression, payload = row
        data = bytes(payload)
        return zlib.decompress(data) if compression == "zlib" else data


class GCSRawStore:
    def __init__(self, bucket_name: str, prefix: str = "raw") -> None:
        try:
            from google.cloud import storage  # type: ignore
        except ImportError as exc:
            raise RuntimeError("GCS RAW backend requires: pip install 'geopolitical-watch[gcp]'") from exc
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.prefix = prefix.strip("/")

    def put(self, source_id: str, collected_at: str, payload: bytes, extension: str) -> tuple[str, str]:
        digest = hashlib.sha256(payload).hexdigest()
        key = "/".join(part for part in (self.prefix, source_id, collected_at[:10], f"{digest}.{extension}") if part)
        blob = self.bucket.blob(key)
        if not blob.exists(self.client):
            blob.upload_from_string(payload, content_type=_content_type(extension), if_generation_match=0)
        return f"gs://{self.bucket.name}/{key}", digest


def _database_url() -> str:
    return (os.environ.get("GEOWATCH_DB_URL") or os.environ.get("DATABASE_URL") or "").strip()


def open_raw_store(location: str | Path | None = None):
    bucket = os.environ.get("GEOWATCH_RAW_BUCKET")
    if bucket:
        return GCSRawStore(bucket, os.environ.get("GEOWATCH_RAW_PREFIX", "raw"))
    backend = os.environ.get("GEOWATCH_RAW_BACKEND", "").strip().casefold()
    db_url = _database_url()
    if backend in {"postgres", "postgresql"}:
        if not db_url:
            raise RuntimeError("GEOWATCH_DB_URL or DATABASE_URL is required for PostgreSQL RAW storage")
        return PostgresRawStore(db_url)
    value = str(location) if location is not None else os.environ.get("GEOWATCH_RAW") or "data/raw"
    if value.startswith("gs://"):
        bucket_and_prefix = value[5:].split("/", 1)
        return GCSRawStore(bucket_and_prefix[0], bucket_and_prefix[1] if len(bucket_and_prefix) > 1 else "raw")
    return LocalRawStore(value)


def raw_backend_name(location: str | Path | None = None) -> str:
    bucket = os.environ.get("GEOWATCH_RAW_BUCKET")
    backend = os.environ.get("GEOWATCH_RAW_BACKEND", "").strip().casefold()
    value = str(location) if location is not None else os.environ.get("GEOWATCH_RAW") or "data/raw"
    if bucket or value.startswith("gs://"):
        return "gcs"
    if backend in {"postgres", "postgresql"}:
        return "postgresql-compressed"
    return "filesystem"


def reset_raw_schema_cache_for_tests() -> None:
    with _RAW_SCHEMA_LOCK:
        _RAW_SCHEMA_READY.clear()


def _content_type(extension: str) -> str:
    ext = extension.casefold().lstrip(".")
    return {"json": "application/json", "csv": "text/csv", "xml": "application/xml", "txt": "text/plain"}.get(ext, "application/octet-stream")

from __future__ import annotations

import hashlib
import json
import os
import threading
import zlib
from pathlib import Path

_RAW_SCHEMA_LOCK = threading.Lock()
_RAW_SCHEMA_READY: set[str] = set()


def _observation_id(source_id: str, digest: str, collected_at: str, collector_id: str | None, source_url: str | None) -> str:
    seed = f"{source_id}|{digest}|{collected_at}|{collector_id or ''}|{source_url or ''}"
    return "rawobs_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


class LocalRawStore:
    def __init__(self, root: str | Path = "data/raw") -> None:
        self.root = Path(root)

    def put(
        self,
        source_id: str,
        collected_at: str,
        payload: bytes,
        extension: str,
        *,
        collector_id: str | None = None,
        source_url: str | None = None,
    ) -> tuple[str, str]:
        digest = hashlib.sha256(payload).hexdigest()
        path = self.root / source_id / collected_at[:10] / f"{digest}.{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(payload)
        self._record_observation(
            source_id=source_id,
            digest=digest,
            collected_at=collected_at,
            collector_id=collector_id,
            source_url=source_url,
            raw_ref=str(path),
            bytes_count=len(payload),
        )
        return str(path), digest

    def _record_observation(
        self,
        *,
        source_id: str,
        digest: str,
        collected_at: str,
        collector_id: str | None,
        source_url: str | None,
        raw_ref: str,
        bytes_count: int,
    ) -> None:
        ledger = self.root / "_ledger" / "observations.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        obs_id = _observation_id(source_id, digest, collected_at, collector_id, source_url)
        record = {
            "observation_id": obs_id,
            "source_id": source_id,
            "sha256": digest,
            "timestamp": collected_at,
            "collector": collector_id,
            "source_url": source_url,
            "raw_ref": raw_ref,
            "bytes": bytes_count,
        }
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

        index = self.root / "_ledger" / "index" / source_id / f"{digest}.json"
        index.parent.mkdir(parents=True, exist_ok=True)
        previous: dict[str, object] = {}
        if index.exists():
            try:
                previous = json.loads(index.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                previous = {}
        first_seen = str(previous.get("first_seen") or collected_at)
        last_seen = max(str(previous.get("last_seen") or collected_at), collected_at)
        payload_index = {
            "source_id": source_id,
            "sha256": digest,
            "first_seen": min(first_seen, collected_at),
            "last_seen": last_seen,
            "first_collector": previous.get("first_collector") or collector_id,
            "last_collector": collector_id,
            "raw_ref": previous.get("raw_ref") or raw_ref,
        }
        tmp = index.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload_index, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(index)


class PostgresRawStore:
    """Compressed immutable raw payloads plus append-only observation provenance."""

    def __init__(self, dsn: str) -> None:
        if not dsn.startswith(("postgresql://", "postgres://")):
            raise ValueError("PostgresRawStore requires a PostgreSQL DSN")
        self.dsn = dsn
        self._schema_key = hashlib.sha256(dsn.encode("utf-8")).hexdigest()

    def _ensure_table(self, db) -> None:  # type: ignore[no-untyped-def]
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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS raw_evidence_observations (
                        observation_id TEXT PRIMARY KEY,
                        source_id TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        observed_at TIMESTAMPTZ NOT NULL,
                        collector_id TEXT,
                        source_url TEXT,
                        raw_ref TEXT NOT NULL,
                        bytes BIGINT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        FOREIGN KEY(source_id, sha256) REFERENCES raw_payloads(source_id, sha256)
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_raw_evidence_observations_source_time
                    ON raw_evidence_observations(source_id, observed_at DESC)
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS raw_evidence_index (
                        source_id TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        first_seen_at TIMESTAMPTZ NOT NULL,
                        last_seen_at TIMESTAMPTZ NOT NULL,
                        first_collector_id TEXT,
                        last_collector_id TEXT,
                        raw_ref TEXT NOT NULL,
                        observation_count BIGINT NOT NULL DEFAULT 1,
                        PRIMARY KEY(source_id, sha256),
                        FOREIGN KEY(source_id, sha256) REFERENCES raw_payloads(source_id, sha256)
                    )
                """)
            db.commit()
            _RAW_SCHEMA_READY.add(self._schema_key)

    def put(
        self,
        source_id: str,
        collected_at: str,
        payload: bytes,
        extension: str,
        *,
        collector_id: str | None = None,
        source_url: str | None = None,
    ) -> tuple[str, str]:
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PostgreSQL RAW backend requires psycopg") from exc
        digest = hashlib.sha256(payload).hexdigest()
        compressed = zlib.compress(payload, level=6)
        ref = f"pgraw://{source_id}/{collected_at[:10]}/{digest}.{extension}"
        obs_id = _observation_id(source_id, digest, collected_at, collector_id, source_url)
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
                cur.execute("""
                    INSERT INTO raw_evidence_observations(
                        observation_id, source_id, sha256, observed_at,
                        collector_id, source_url, raw_ref, bytes
                    ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(observation_id) DO NOTHING
                """, (
                    obs_id, source_id, digest, collected_at,
                    collector_id, source_url, ref, len(payload),
                ))
                inserted = cur.rowcount > 0
                cur.execute("""
                    INSERT INTO raw_evidence_index(
                        source_id, sha256, first_seen_at, last_seen_at,
                        first_collector_id, last_collector_id, raw_ref, observation_count
                    ) VALUES(%s,%s,%s,%s,%s,%s,%s,1)
                    ON CONFLICT(source_id, sha256) DO UPDATE SET
                        first_seen_at=LEAST(raw_evidence_index.first_seen_at, EXCLUDED.first_seen_at),
                        last_seen_at=GREATEST(raw_evidence_index.last_seen_at, EXCLUDED.last_seen_at),
                        first_collector_id=COALESCE(raw_evidence_index.first_collector_id, EXCLUDED.first_collector_id),
                        last_collector_id=EXCLUDED.last_collector_id,
                        observation_count=raw_evidence_index.observation_count + %s
                """, (
                    source_id, digest, collected_at, collected_at,
                    collector_id, collector_id, ref, 1 if inserted else 0,
                ))
            db.commit()
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



class S3RawStore:
    """Content-addressed RAW storage for S3-compatible providers such as Neon Object Storage."""

    def __init__(self, bucket_name: str, prefix: str = "raw") -> None:
        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise RuntimeError("S3 RAW backend requires: pip install 'geopolitical-watch[s3]'") from exc
        self.bucket_name = bucket_name
        self.prefix = prefix.strip("/")
        self.client = boto3.client(
            "s3",
            region_name=os.environ.get("AWS_REGION") or None,
            endpoint_url=os.environ.get("AWS_ENDPOINT_URL_S3") or None,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY") or None,
        )

    def put(
        self,
        source_id: str,
        collected_at: str,
        payload: bytes,
        extension: str,
        *,
        collector_id: str | None = None,
        source_url: str | None = None,
    ) -> tuple[str, str]:
        digest = hashlib.sha256(payload).hexdigest()
        filename = f"{digest}.{extension}.zlib"
        key = "/".join(part for part in (self.prefix, "payloads", source_id, filename) if part)
        compressed = zlib.compress(payload, level=6)
        exists = False
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            exists = True
        except Exception as exc:
            response = getattr(exc, "response", {}) or {}
            code = str((response.get("Error") or {}).get("Code") or "")
            status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            if code not in {"404", "NoSuchKey", "NotFound"} and status != 404:
                raise
        if not exists:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=compressed,
                ContentType="application/octet-stream",
                Metadata={
                    "sha256": digest,
                    "source-id": source_id,
                    "original-extension": extension,
                    "compression": "zlib",
                    "original-bytes": str(len(payload)),
                },
            )
        ref = f"s3://{self.bucket_name}/{key}"
        obs_id = _observation_id(source_id, digest, collected_at, collector_id, source_url)
        observation_key = "/".join(part for part in (
            self.prefix, "_ledger", "observations", source_id, collected_at[:10], f"{obs_id}.json"
        ) if part)
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=observation_key,
            Body=json.dumps({
                "observation_id": obs_id,
                "source_id": source_id,
                "sha256": digest,
                "timestamp": collected_at,
                "collector": collector_id,
                "source_url": source_url,
                "raw_ref": ref,
                "bytes": len(payload),
                "stored_bytes": len(compressed),
            }, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            ContentType="application/json",
        )
        return ref, digest


class GCSRawStore:
    def __init__(self, bucket_name: str, prefix: str = "raw") -> None:
        try:
            from google.cloud import storage  # type: ignore
        except ImportError as exc:
            raise RuntimeError("GCS RAW backend requires: pip install 'geopolitical-watch[gcp]'") from exc
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.prefix = prefix.strip("/")

    def put(
        self,
        source_id: str,
        collected_at: str,
        payload: bytes,
        extension: str,
        *,
        collector_id: str | None = None,
        source_url: str | None = None,
    ) -> tuple[str, str]:
        digest = hashlib.sha256(payload).hexdigest()
        key = "/".join(part for part in (self.prefix, source_id, collected_at[:10], f"{digest}.{extension}") if part)
        blob = self.bucket.blob(key)
        if not blob.exists(self.client):
            blob.upload_from_string(payload, content_type=_content_type(extension), if_generation_match=0)
        ref = f"gs://{self.bucket.name}/{key}"
        obs_id = _observation_id(source_id, digest, collected_at, collector_id, source_url)
        observation_key = "/".join(part for part in (
            self.prefix, "_ledger", "observations", source_id, collected_at[:10], f"{obs_id}.json"
        ) if part)
        observation = self.bucket.blob(observation_key)
        if not observation.exists(self.client):
            observation.upload_from_string(
                json.dumps({
                    "observation_id": obs_id,
                    "source_id": source_id,
                    "sha256": digest,
                    "timestamp": collected_at,
                    "collector": collector_id,
                    "source_url": source_url,
                    "raw_ref": ref,
                    "bytes": len(payload),
                }, ensure_ascii=False, sort_keys=True),
                content_type="application/json",
                if_generation_match=0,
            )
        return ref, digest


def _database_url() -> str:
    return (os.environ.get("GEOWATCH_DB_URL") or os.environ.get("DATABASE_URL") or "").strip()


def open_raw_store(location: str | Path | None = None):
    bucket = os.environ.get("GEOWATCH_RAW_BUCKET")
    if bucket:
        return GCSRawStore(bucket, os.environ.get("GEOWATCH_RAW_PREFIX", "raw"))
    backend = os.environ.get("GEOWATCH_RAW_BACKEND", "").strip().casefold()
    s3_bucket = os.environ.get("GEOWATCH_RAW_S3_BUCKET", "").strip()
    if backend in {"s3", "neon", "neon-object-storage"} or s3_bucket:
        if not s3_bucket:
            raise RuntimeError("GEOWATCH_RAW_S3_BUCKET is required for S3-compatible RAW storage")
        return S3RawStore(s3_bucket, os.environ.get("GEOWATCH_RAW_PREFIX", "raw"))
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
    s3_bucket = os.environ.get("GEOWATCH_RAW_S3_BUCKET", "").strip()
    value = str(location) if location is not None else os.environ.get("GEOWATCH_RAW") or "data/raw"
    if bucket or value.startswith("gs://"):
        return "gcs"
    if backend in {"s3", "neon", "neon-object-storage"} or s3_bucket:
        return "s3-compatible"
    if backend in {"postgres", "postgresql"}:
        return "postgresql-compressed"
    return "filesystem"


def reset_raw_schema_cache_for_tests() -> None:
    with _RAW_SCHEMA_LOCK:
        _RAW_SCHEMA_READY.clear()


def _content_type(extension: str) -> str:
    ext = extension.casefold().lstrip(".")
    return {
        "json": "application/json",
        "csv": "text/csv",
        "xml": "application/xml",
        "txt": "text/plain",
        "html": "text/html",
        "pdf": "application/pdf",
    }.get(ext, "application/octet-stream")

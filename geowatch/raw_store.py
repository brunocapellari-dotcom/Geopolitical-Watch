from __future__ import annotations

import hashlib
import os
from pathlib import Path


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


def open_raw_store(location: str | Path | None = None):
    bucket = os.environ.get("GEOWATCH_RAW_BUCKET")
    if bucket:
        return GCSRawStore(bucket, os.environ.get("GEOWATCH_RAW_PREFIX", "raw"))
    value = str(location) if location is not None else os.environ.get("GEOWATCH_RAW") or "data/raw"
    if value.startswith("gs://"):
        bucket_and_prefix = value[5:].split("/", 1)
        return GCSRawStore(bucket_and_prefix[0], bucket_and_prefix[1] if len(bucket_and_prefix) > 1 else "raw")
    return LocalRawStore(value)


def raw_backend_name(location: str | Path | None = None) -> str:
    bucket = os.environ.get("GEOWATCH_RAW_BUCKET")
    value = str(location) if location is not None else os.environ.get("GEOWATCH_RAW") or "data/raw"
    return "gcs" if bucket or value.startswith("gs://") else "filesystem"


def _content_type(extension: str) -> str:
    ext = extension.casefold().lstrip(".")
    return {"json": "application/json", "csv": "text/csv", "xml": "application/xml", "txt": "text/plain"}.get(ext, "application/octet-stream")

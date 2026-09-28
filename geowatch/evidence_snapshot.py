from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .http import HttpResponse, get, validate_web_url
from .raw_store import open_raw_store


@dataclass(frozen=True)
class EvidenceSnapshot:
    source_id: str
    original_url: str
    final_url: str
    collected_at: str
    content_type: str | None
    bytes: int
    sha256: str
    raw_ref: str
    collector_id: str | None = None
    response_headers: tuple[tuple[str, str], ...] = ()
    capture_method: str = "http"
    method_version: str = "geowatch-evidence-snapshot-v1"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def capture_url(
    source_id: str,
    url: str,
    *,
    collected_at: str | None = None,
    collector_id: str | None = None,
    raw_store=None,
    timeout: int = 60,
    retries: int = 2,
) -> EvidenceSnapshot:
    original_url = validate_web_url(url)
    response = get(original_url, timeout=timeout, retries=retries)
    timestamp = collected_at or datetime.now(timezone.utc).isoformat()
    return snapshot_response(
        source_id,
        original_url,
        response,
        collected_at=timestamp,
        collector_id=collector_id,
        raw_store=raw_store,
    )


def snapshot_response(
    source_id: str,
    original_url: str,
    response: HttpResponse,
    *,
    collected_at: str,
    collector_id: str | None = None,
    raw_store=None,
) -> EvidenceSnapshot:
    original_url = validate_web_url(original_url)
    final_url = validate_web_url(response.url)
    extension = _extension_for(response.content_type)
    store = raw_store or open_raw_store()
    raw_ref, digest = store.put(
        source_id,
        collected_at,
        response.payload,
        extension,
        collector_id=collector_id,
        source_url=final_url,
    )
    calculated = hashlib.sha256(response.payload).hexdigest()
    if digest != calculated:
        raise RuntimeError("raw store digest mismatch")
    return EvidenceSnapshot(
        source_id=source_id,
        original_url=original_url,
        final_url=final_url,
        collected_at=collected_at,
        content_type=response.content_type,
        bytes=len(response.payload),
        sha256=digest,
        raw_ref=raw_ref,
        collector_id=collector_id,
        response_headers=response.headers,
    )


def _extension_for(content_type: str | None) -> str:
    value = (content_type or "").split(";", 1)[0].strip().casefold()
    return {
        "application/json": "json",
        "application/geo+json": "json",
        "text/html": "html",
        "application/xhtml+xml": "html",
        "application/xml": "xml",
        "text/xml": "xml",
        "text/csv": "csv",
        "text/plain": "txt",
        "application/pdf": "pdf",
    }.get(value, "bin")

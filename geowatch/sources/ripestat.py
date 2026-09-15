from __future__ import annotations

import json
from urllib.parse import quote

from ..core import stable_event_id, utc_now_iso
from ..http import get
from ..models import Event

_BASE = "https://stat.ripe.net/data/routing-status/data.json"


def collect(*, resource: str, timeout: int = 45) -> tuple[bytes, str]:
    value = _resource(resource)
    response = get(_BASE, query={"resource": value, "sourceapp": "geopolitical-watch"}, timeout=timeout)
    return response.payload, response.url


def parse(
    payload: bytes,
    *,
    source_id: str = "ripestat_bgp",
    collected_at: str | None = None,
    raw_ref: str | None = None,
    visibility_threshold: float = 0.85,
) -> list[Event]:
    body = json.loads(payload.decode("utf-8"))
    data = body.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError("RIPEstat payload missing data object")
    resource = str(data.get("resource") or data.get("resource_requested") or "unknown").strip()
    visibility = ((data.get("visibility") or {}).get("v4") or {}) if isinstance(data.get("visibility"), dict) else {}
    seeing = _float(visibility.get("ris_peers_seeing"))
    total = _float(visibility.get("total_ris_peers"))
    if seeing is None or total is None or total <= 0:
        return []
    ratio = seeing / total
    if ratio >= max(0.0, min(float(visibility_threshold), 1.0)):
        return []
    collected = collected_at or utc_now_iso()
    percentage = round(ratio * 100, 1)
    title = f"BGP visibility degradation — {resource} visible to {percentage}% of RIS peers"
    return [Event(
        event_id=stable_event_id(source_id, resource, title, collected, None),
        source_id=source_id,
        source_kind="sensor",
        source_event_id=f"{resource}:{collected[:16]}",
        title=title,
        event_type="bgp_visibility_degradation",
        reference_at=collected,
        collected_at=collected,
        verification_level="sensor_signal",
        evidence_class="observed",
        source_url=f"https://stat.ripe.net/{quote(resource, safe='')}",
        publisher="RIPE NCC RIPEstat",
        impact_areas=("infrastructure",),
        impact_evidence_class="inferred",
        raw_ref=raw_ref,
    )]


def _resource(value: str) -> str:
    resource = str(value or "").strip().upper()
    if not resource or len(resource) > 80:
        raise ValueError("RIPEstat resource is required")
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:/-")
    if any(char not in allowed for char in resource):
        raise ValueError("invalid RIPEstat resource")
    return resource


def _float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

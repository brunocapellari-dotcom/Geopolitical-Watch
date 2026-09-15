from __future__ import annotations

import json
from datetime import datetime, timezone

from ..core import stable_event_id, utc_now_iso
from ..http import get
from ..models import Event

_FEED_BASE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"
_QUERY_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
_ALLOWED_FEEDS = {
    "significant_hour", "significant_day", "significant_week", "significant_month",
    "4.5_hour", "4.5_day", "4.5_week", "4.5_month",
    "2.5_hour", "2.5_day", "2.5_week", "2.5_month",
    "1.0_hour", "1.0_day", "1.0_week", "1.0_month",
    "all_hour", "all_day", "all_week", "all_month",
}


def collect(*, feed: str = "significant_day", timeout: int = 60) -> tuple[bytes, str]:
    name = str(feed).strip().casefold()
    if name not in _ALLOWED_FEEDS:
        raise ValueError("unsupported USGS earthquake feed")
    response = get(f"{_FEED_BASE}/{name}.geojson", timeout=timeout)
    return response.payload, response.url


def collect_range(
    *,
    start: str,
    end: str,
    min_magnitude: float = 4.5,
    limit: int = 20000,
    timeout: int = 90,
) -> tuple[bytes, str]:
    magnitude = max(-1.0, min(float(min_magnitude), 10.0))
    bounded_limit = max(1, min(int(limit), 20000))
    response = get(
        _QUERY_URL,
        query={
            "format": "geojson",
            "starttime": str(start),
            "endtime": str(end),
            "minmagnitude": str(magnitude),
            "orderby": "time-asc",
            "limit": bounded_limit,
        },
        timeout=timeout,
    )
    return response.payload, response.url


def parse(
    payload: bytes,
    *,
    source_id: str = "usgs_earthquakes",
    collected_at: str | None = None,
    raw_ref: str | None = None,
) -> list[Event]:
    body = json.loads(payload.decode("utf-8"))
    if body.get("type") != "FeatureCollection":
        raise ValueError("USGS payload is not a GeoJSON FeatureCollection")
    collected = collected_at or utc_now_iso()
    events: list[Event] = []
    for feature in body.get("features") or []:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if not isinstance(props, dict) or not isinstance(coords, list) or len(coords) < 2:
            continue
        lon = _float(coords[0]); lat = _float(coords[1])
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        source_event_id = str(feature.get("id") or "").strip() or None
        mag = _float(props.get("mag"))
        place = str(props.get("place") or "Unknown location").strip()
        title = f"M{mag:g} earthquake — {place}" if mag is not None else f"Earthquake — {place}"
        reference = _epoch_ms(props.get("time"), collected)
        event_url = str(props.get("url") or "").strip() or None
        events.append(Event(
            event_id=stable_event_id(source_id, source_event_id, title, reference, None),
            source_id=source_id,
            source_kind="sensor",
            source_event_id=source_event_id,
            title=title,
            event_type="earthquake",
            reference_at=reference,
            collected_at=collected,
            verification_level="sensor_signal",
            evidence_class="observed",
            region=place,
            latitude=lat,
            longitude=lon,
            source_url=event_url,
            publisher="USGS Earthquake Hazards Program",
            impact_areas=("infrastructure", "humanitarian"),
            impact_evidence_class="inferred",
            raw_ref=raw_ref,
        ))
    return events


def _epoch_ms(value: object, fallback: str) -> str:
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return fallback


def _float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

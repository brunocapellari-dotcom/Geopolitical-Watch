from __future__ import annotations

import json
from datetime import datetime, timezone

from ..core import infer_impact_areas, stable_event_id, utc_now_iso
from ..http import get
from ..models import Event

DEFAULT_URL = "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/latest"


def collect(*, timeout: int = 60, query: dict[str, str | int] | None = None) -> tuple[bytes, str]:
    response = get(DEFAULT_URL, timeout=timeout, query=query)
    return response.payload, response.url


def parse(payload: bytes, *, source_id: str = "gdacs_context", collected_at: str | None = None, raw_ref: str | None = None) -> list[Event]:
    body = json.loads(payload.decode("utf-8"))
    rows = _rows(body)
    collected = collected_at or utc_now_iso()
    events: list[Event] = []
    for row in rows:
        props = row.get("properties") if isinstance(row.get("properties"), dict) else row
        if not isinstance(props, dict):
            continue
        event_id = _text(props.get("eventid") or props.get("event_id") or props.get("id"))
        event_type = _text(props.get("eventtype") or props.get("event_type") or props.get("type")) or "disaster"
        name = _text(props.get("name") or props.get("title") or props.get("eventname"))
        country = _text(props.get("country") or props.get("countryname"))
        alert = _text(props.get("alertlevel") or props.get("alert_level"))
        title = name or f"GDACS {event_type}{' ' + alert if alert else ''}".strip()
        reference_at = _timestamp(props.get("fromdate") or props.get("todate") or props.get("date") or props.get("lastupdate"), collected)
        latitude, longitude = _point(row)
        url = _text(props.get("url") or props.get("link") or props.get("web"))
        impacts = list(infer_impact_areas(title))
        for area in ("humanitarian", "infrastructure"):
            if area not in impacts:
                impacts.append(area)
        source_event_id = event_id or f"{event_type}:{reference_at}:{country or ''}:{title}"
        events.append(Event(
            event_id=stable_event_id(source_id, source_event_id, title, reference_at, country),
            source_id=source_id,
            source_kind="institutional",
            source_event_id=source_event_id,
            title=title,
            event_type=f"gdacs_{event_type.casefold().replace(' ', '_')}",
            reference_at=reference_at,
            published_at=reference_at,
            collected_at=collected,
            verification_level="curated_report",
            country=country,
            location=name or country,
            latitude=latitude,
            longitude=longitude,
            location_source="reported",
            geolocation_method="source_geometry" if latitude is not None and longitude is not None else None,
            geolocation_confidence=0.95 if latitude is not None and longitude is not None else None,
            source_url=url,
            publisher="gdacs.org",
            impact_areas=tuple(impacts),  # type: ignore[arg-type]
            raw_ref=raw_ref,
        ))
    return events


def _rows(body: object) -> list[dict]:
    if isinstance(body, list):
        return [row for row in body if isinstance(row, dict)]
    if not isinstance(body, dict):
        return []
    for key in ("features", "data", "results", "events", "items"):
        value = body.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _point(row: dict) -> tuple[float | None, float | None]:
    geometry = row.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        return None, None
    coords = geometry.get("coordinates")
    if not isinstance(coords, list) or len(coords) < 2:
        return None, None
    try:
        return float(coords[1]), float(coords[0])
    except (TypeError, ValueError):
        return None, None


def _timestamp(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return text


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

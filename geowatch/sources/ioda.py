from __future__ import annotations

import json
from datetime import datetime, timezone

from ..core import stable_event_id, utc_now_iso
from ..http import get
from ..models import Event

_BASE = "https://api.ioda.inetintel.cc.gatech.edu/v2/outages"
_ALLOWED_ENDPOINTS = {"alerts", "events"}


def collect(*, endpoint: str = "alerts", limit: int = 100, timeout: int = 60) -> tuple[bytes, str]:
    name = str(endpoint).strip().casefold()
    if name not in _ALLOWED_ENDPOINTS:
        raise ValueError("unsupported IODA outage endpoint")
    response = get(f"{_BASE}/{name}", query={"limit": max(1, min(int(limit), 500))}, timeout=timeout)
    return response.payload, response.url


def parse(
    payload: bytes,
    *,
    source_id: str = "ioda_outages",
    collected_at: str | None = None,
    raw_ref: str | None = None,
) -> list[Event]:
    body = json.loads(payload.decode("utf-8"))
    rows = _rows(body)
    collected = collected_at or utc_now_iso()
    events: list[Event] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        entity = _entity(row)
        started = _time(row, collected)
        source_event_id = str(row.get("id") or row.get("event_id") or row.get("alert_id") or "").strip()
        if not source_event_id:
            source_event_id = f"{entity}:{started}"
        score = _number(row.get("score") or row.get("severity") or row.get("level"))
        title = f"Internet connectivity outage signal — {entity}"
        if score is not None:
            title += f" (score {score:g})"
        country = _country(row)
        events.append(Event(
            event_id=stable_event_id(source_id, source_event_id, title, started, country),
            source_id=source_id,
            source_kind="sensor",
            source_event_id=source_event_id,
            title=title,
            event_type="internet_connectivity_outage_signal",
            reference_at=started,
            collected_at=collected,
            verification_level="sensor_signal",
            evidence_class="observed",
            country=country,
            region=entity if entity != country else None,
            publisher="Georgia Tech IODA",
            impact_areas=("infrastructure",),
            impact_evidence_class="inferred",
            raw_ref=raw_ref,
        ))
    return events


def _rows(body: object) -> list[object]:
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        raise ValueError("IODA payload must be a JSON object or list")
    data = body.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("alerts", "events", "results", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    for key in ("alerts", "events", "results", "items"):
        if isinstance(body.get(key), list):
            return body[key]
    return []


def _entity(row: dict) -> str:
    for value in (
        row.get("entityName"), row.get("entity_name"), row.get("name"),
        row.get("entityCode"), row.get("entity_code"), row.get("entity"),
    ):
        if value not in (None, ""):
            return str(value).strip()
    return "unknown entity"


def _country(row: dict) -> str | None:
    for key in ("country", "countryCode", "country_code"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return None


def _time(row: dict, fallback: str) -> str:
    for key in ("start", "startTime", "start_time", "timestamp", "time", "from"):
        value = row.get(key)
        parsed = _parse_time(value)
        if parsed:
            return parsed
    return fallback


def _parse_time(value: object) -> str | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).strip().isdigit():
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000.0
            return datetime.fromtimestamp(number, tz=timezone.utc).isoformat()
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def _number(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None

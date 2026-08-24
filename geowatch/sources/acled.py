from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from ..core import infer_impact_areas, stable_event_id, utc_now_iso
from ..http import get, post_form
from ..models import Event

TOKEN_URL = "https://acleddata.com/oauth/token"
DATA_URL = "https://acleddata.com/api/acled/read"


def access_token(*, timeout: int = 60) -> str:
    token = os.environ.get("ACLED_ACCESS_TOKEN")
    if token:
        return token
    username = os.environ.get("ACLED_USERNAME")
    password = os.environ.get("ACLED_PASSWORD")
    if not username or not password:
        raise RuntimeError("ACLED requires ACLED_ACCESS_TOKEN or ACLED_USERNAME/ACLED_PASSWORD")
    response = post_form(TOKEN_URL, {
        "username": username,
        "password": password,
        "grant_type": "password",
        "client_id": "acled",
        "scope": "authenticated",
    }, timeout=timeout)
    body = json.loads(response.payload.decode("utf-8"))
    token = body.get("access_token")
    if not token:
        raise RuntimeError("ACLED OAuth response missing access_token")
    return str(token)


def collect(*, query: dict[str, str | int] | None = None, limit: int = 5000, cursor: str | int | None = None, token: str | None = None, timeout: int = 90) -> tuple[bytes, str]:
    params: dict[str, str | int] = {"limit": min(max(limit, 1), 5000), "_format": "json", "with_total": "true"}
    params.update(query or {})
    if cursor is not None:
        params["cursor"] = cursor
    auth = token or access_token(timeout=timeout)
    response = get(DATA_URL, headers={"Authorization": f"Bearer {auth}"}, timeout=timeout, query=params)
    return response.payload, response.url


def collect_all(*, query: dict[str, str | int] | None = None, limit: int = 5000, max_pages: int = 200, timeout: int = 90) -> tuple[list[bytes], list[str]]:
    """Cursor-based pagination, preferred over page pagination for long-lived automation."""
    token = access_token(timeout=timeout)
    cursor: str | int | None = 0
    payloads: list[bytes] = []
    urls: list[str] = []
    seen: set[str] = set()
    for _ in range(max(1, max_pages)):
        payload, url = collect(query=query, limit=limit, cursor=cursor, token=token, timeout=timeout)
        payloads.append(payload)
        urls.append(url)
        body = json.loads(payload.decode("utf-8"))
        next_cursor = body.get("next_cursor") if isinstance(body, dict) else None
        if next_cursor in (None, "", 0, "0"):
            break
        key = str(next_cursor)
        if key in seen:
            raise RuntimeError("ACLED cursor pagination repeated a cursor")
        seen.add(key)
        cursor = next_cursor
    else:
        raise RuntimeError("ACLED pagination reached max_pages before next_cursor became null")
    return payloads, urls


def parse(payload: bytes, *, source_id: str = "acled_events", collected_at: str | None = None, raw_ref: str | None = None) -> list[Event]:
    body = json.loads(payload.decode("utf-8"))
    rows = body.get("data", body if isinstance(body, list) else [])
    if not isinstance(rows, list):
        raise ValueError("ACLED payload missing data list")
    collected = collected_at or utc_now_iso()
    events: list[Event] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_event_id = _text(row.get("event_id_cnty") or row.get("event_id_no_cnty") or row.get("event_id"))
        event_type = _text(row.get("sub_event_type") or row.get("event_type")) or "coded_conflict_event"
        location = _text(row.get("location"))
        country = _text(row.get("country"))
        admin1 = _text(row.get("admin1"))
        title = " — ".join(part for part in (event_type, location, country) if part)
        reference_at = _event_date(row.get("event_date"), collected)
        actor1 = _text(row.get("actor1"))
        actor2 = _text(row.get("actor2"))
        actors = tuple(value for value in (actor1, actor2) if value)
        latitude = _float(row.get("latitude"))
        longitude = _float(row.get("longitude"))
        fatalities = _int(row.get("fatalities"))
        event_key = source_event_id or f"{reference_at}:{country or ''}:{location or ''}:{event_type}:{actor1 or ''}:{actor2 or ''}"
        events.append(Event(
            event_id=stable_event_id(source_id, event_key, title, reference_at, country),
            source_id=source_id,
            source_kind="coded",
            source_event_id=event_key,
            title=title,
            event_type=event_type.casefold().replace(" ", "_"),
            reference_at=reference_at,
            collected_at=collected,
            verification_level="research_coded",
            country=country,
            region=admin1,
            latitude=latitude,
            longitude=longitude,
            fatalities_best=fatalities,
            actors=actors,
            publisher="ACLED",
            impact_areas=infer_impact_areas(title),
            raw_ref=raw_ref,
        ))
    return events


def _event_date(value: object, fallback: str) -> str:
    text = _text(value)
    if not text:
        return fallback
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
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


def _float(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    try:
        return int(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None

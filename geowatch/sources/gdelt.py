from __future__ import annotations

import json
from datetime import datetime, timezone

from ..core import infer_impact_areas, publisher_from_url, stable_event_id, utc_now_iso
from ..http import get
from ..models import Event

DEFAULT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_QUERY = '(war OR conflict OR airstrike OR missile OR shelling OR invasion OR "drone strike" OR ceasefire OR blockade)'


def collect(*, query: str = DEFAULT_QUERY, timespan: str = "24H", maxrecords: int = 250, timeout: int = 60, start_datetime: str | None = None, end_datetime: str | None = None) -> tuple[bytes, str]:
    params: dict[str, str | int] = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": min(max(maxrecords, 1), 250),
        "format": "json",
        "sort": "DateDesc",
    }
    if start_datetime or end_datetime:
        if start_datetime:
            params["startdatetime"] = start_datetime
        if end_datetime:
            params["enddatetime"] = end_datetime
    else:
        params["timespan"] = timespan
    response = get(DEFAULT_URL, timeout=timeout, query=params)
    return response.payload, response.url


def parse(payload: bytes, *, source_id: str = "gdelt_doc", collected_at: str | None = None, raw_ref: str | None = None) -> list[Event]:
    body = json.loads(payload.decode("utf-8"))
    rows = body.get("articles", [])
    if not isinstance(rows, list):
        raise ValueError("GDELT payload missing articles list")
    collected = collected_at or utc_now_iso()
    events: list[Event] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = _text(row.get("title"))
        url = _text(row.get("url"))
        if not title:
            continue
        published = _parse_timestamp(_text(row.get("seendate"))) or collected
        publisher = publisher_from_url(url)
        events.append(Event(
            event_id=stable_event_id(source_id, url, title, published, None),
            source_id=source_id,
            source_kind="news",
            source_event_id=url,
            title=title,
            event_type="media_report",
            reference_at=published,
            published_at=published,
            collected_at=collected,
            verification_level="osint_signal",
            source_url=url,
            publisher=publisher,
            impact_areas=infer_impact_areas(title),
            raw_ref=raw_ref,
        ))
    return events


def _parse_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    return value


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

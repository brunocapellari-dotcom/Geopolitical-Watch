from __future__ import annotations

import json
import os

from ..core import infer_impact_areas, publisher_from_url, stable_event_id, utc_now_iso
from ..http import get
from ..models import Event

BASE_URL = "https://api.reliefweb.int/v2/reports"


def collect(*, appname: str | None = None, query: str = "conflict war hostilities displacement", limit: int = 100, timeout: int = 60) -> tuple[bytes, str]:
    appname = appname or os.environ.get("RELIEFWEB_APPNAME")
    if not appname:
        raise RuntimeError("RELIEFWEB_APPNAME is required")
    response = get(BASE_URL, timeout=timeout, query={
        "appname": appname,
        "profile": "full",
        "preset": "latest",
        "limit": min(max(limit, 1), 1000),
        "query[value]": query,
    })
    return response.payload, response.url


def parse(payload: bytes, *, source_id: str = "reliefweb", collected_at: str | None = None, raw_ref: str | None = None) -> list[Event]:
    body = json.loads(payload.decode("utf-8"))
    rows = body.get("data", [])
    if not isinstance(rows, list):
        raise ValueError("ReliefWeb payload missing data list")
    collected = collected_at or utc_now_iso()
    events: list[Event] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        fields = row.get("fields", {}) if isinstance(row.get("fields", {}), dict) else {}
        title = _text(fields.get("title"))
        if not title:
            continue
        source_event_id = _text(row.get("id"))
        date = fields.get("date", {}) if isinstance(fields.get("date", {}), dict) else {}
        published = _text(date.get("original")) or _text(date.get("created")) or collected
        country = _country(fields)
        source_url = _text(fields.get("origin")) or _text(fields.get("url_alias")) or _text(fields.get("url"))
        publisher = _source_name(fields.get("source")) or publisher_from_url(source_url)
        events.append(Event(
            event_id=stable_event_id(source_id, source_event_id, title, published, country),
            source_id=source_id,
            source_kind="institutional",
            source_event_id=source_event_id,
            title=title,
            event_type="humanitarian_report",
            reference_at=published,
            published_at=published,
            collected_at=collected,
            verification_level="curated_report",
            country=country,
            source_url=source_url,
            publisher=publisher,
            impact_areas=infer_impact_areas(" ".join([title, country or ""])),
            raw_ref=raw_ref,
        ))
    return events


def _country(fields: dict) -> str | None:
    primary = fields.get("primary_country")
    if isinstance(primary, dict):
        return _text(primary.get("name")) or _text(primary.get("shortname"))
    countries = fields.get("country")
    if isinstance(countries, list):
        for item in countries:
            if isinstance(item, dict) and item.get("primary"):
                return _text(item.get("name")) or _text(item.get("shortname"))
        for item in countries:
            if isinstance(item, dict):
                value = _text(item.get("name")) or _text(item.get("shortname"))
                if value:
                    return value
    return None


def _source_name(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    for source in value:
        if isinstance(source, dict):
            name = _text(source.get("shortname")) or _text(source.get("name")) or _text(source.get("longname"))
            if name:
                return name
    return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

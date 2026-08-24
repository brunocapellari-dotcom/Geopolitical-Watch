from __future__ import annotations

import json
import os

from ..core import infer_impact_areas, stable_event_id, utc_now_iso
from ..http import get
from ..models import Event

DEFAULT_BASE = "https://ucdpapi.pcr.uu.se/api/gedevents"
DEFAULT_VERSION = "26.1"


def collect_all(*, token: str | None = None, version: str = DEFAULT_VERSION, pagesize: int = 1000, timeout: int = 90, max_pages: int = 100, start_date: str | None = None, end_date: str | None = None) -> tuple[list[bytes], list[str]]:
    token = token or os.environ.get("UCDP_API_TOKEN")
    if not token:
        raise RuntimeError("UCDP_API_TOKEN is required")
    pages: list[bytes] = []
    urls: list[str] = []
    page = 1
    while page <= max_pages:
        query: dict[str, str | int] = {"pagesize": pagesize, "page": page}
        if start_date:
            query["StartDate"] = start_date
        if end_date:
            query["EndDate"] = end_date
        response = get(f"{DEFAULT_BASE}/{version}", headers={"x-ucdp-access-token": token}, timeout=timeout, query=query)
        pages.append(response.payload)
        urls.append(response.url)
        body = json.loads(response.payload.decode("utf-8"))
        total_pages = _int(body.get("TotalPages"))
        if total_pages is not None and page >= total_pages:
            break
        next_url = body.get("NextPageUrl")
        if not next_url and total_pages is None:
            break
        page += 1
    return pages, urls


def parse(payload: bytes, *, source_id: str = "ucdp_ged", collected_at: str | None = None, raw_ref: str | None = None) -> list[Event]:
    body = json.loads(payload.decode("utf-8"))
    rows = body.get("Result", [])
    if not isinstance(rows, list):
        raise ValueError("UCDP payload missing Result list")
    collected = collected_at or utc_now_iso()
    events: list[Event] = []
    type_map = {1: "state_based_violence", 2: "non_state_violence", 3: "one_sided_violence"}
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_event_id = _text(row.get("id"))
        title = _text(row.get("dyad_name")) or _text(row.get("conflict_name")) or f"UCDP event {source_event_id or 'unknown'}"
        reference = _text(row.get("date_start")) or collected
        country = _text(row.get("country"))
        actors = tuple(v for v in (_text(row.get("side_a")), _text(row.get("side_b"))) if v)
        context = " ".join([title, _text(row.get("where_description")) or ""])
        events.append(Event(
            event_id=stable_event_id(source_id, source_event_id, title, reference, country),
            source_id=source_id,
            source_kind="research",
            source_event_id=source_event_id,
            title=title,
            event_type=type_map.get(_int(row.get("type_of_violence")), "organized_violence"),
            reference_at=reference,
            collected_at=collected,
            verification_level="research_coded",
            country=country,
            region=_text(row.get("region")),
            latitude=_float(row.get("latitude")),
            longitude=_float(row.get("longitude")),
            fatalities_best=_int(row.get("best")),
            actors=actors,
            impact_areas=infer_impact_areas(context),
            raw_ref=raw_ref,
        ))
    return events


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: object) -> int | None:
    try:
        return int(float(str(value))) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float | None:
    try:
        return float(str(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None

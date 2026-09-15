from __future__ import annotations

import csv
import io
import os

from ..core import stable_event_id, utc_now_iso
from ..http import get
from ..models import Event
from ..security_redaction import redact_url

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def collect(*, map_key: str | None = None, sensor: str = "VIIRS_SNPP_NRT", area: str = "world", day_range: int = 1, date: str | None = None, timeout: int = 90) -> tuple[bytes, str]:
    map_key = map_key or os.environ.get("FIRMS_MAP_KEY")
    if not map_key:
        raise RuntimeError("FIRMS_MAP_KEY is required")
    day_range = min(max(day_range, 1), 5)
    request_url = f"{BASE_URL}/{map_key}/{sensor}/{area}/{day_range}"
    if date:
        request_url += f"/{date}"
    response = get(request_url, timeout=timeout)
    # FIRMS places MAP_KEY in the URL path. Provenance must never persist it.
    observed_url = redact_url(response.url, secret_path_values=(map_key,))
    return response.payload, observed_url


def parse(payload: bytes, *, source_id: str = "nasa_firms", collected_at: str | None = None, raw_ref: str | None = None) -> list[Event]:
    """Parse thermal anomalies as contextual sensor signals only.

    A thermal anomaly is not evidence of an attack by itself. It is intentionally
    emitted as `sensor_signal` and must be corroborated before conflict attribution.
    """
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    collected = collected_at or utc_now_iso()
    events: list[Event] = []
    for row in reader:
        lat = _float(row.get("latitude"))
        lon = _float(row.get("longitude"))
        acq_date = (row.get("acq_date") or collected[:10]).strip()
        acq_time = (row.get("acq_time") or "0000").strip().zfill(4)
        reference = f"{acq_date}T{acq_time[:2]}:{acq_time[2:]}:00+00:00"
        source_event_id = f"{lat}:{lon}:{reference}:{row.get('satellite','')}"
        title = f"Thermal anomaly at {lat},{lon}"
        events.append(Event(
            event_id=stable_event_id(source_id, source_event_id, title, reference, None),
            source_id=source_id,
            source_kind="sensor",
            source_event_id=source_event_id,
            title=title,
            event_type="thermal_anomaly",
            reference_at=reference,
            collected_at=collected,
            verification_level="sensor_signal",
            latitude=lat,
            longitude=lon,
            publisher="NASA FIRMS",
            raw_ref=raw_ref,
        ))
    return events


def _float(value: object) -> float | None:
    try:
        return float(str(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None

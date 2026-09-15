from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from ..http import get

_BASE = "https://celestrak.org/NORAD/elements/gp.php"
_ALLOWED_GROUPS = {"military", "active", "stations", "gps-ops", "galileo", "beidou", "glo-ops"}


@dataclass(frozen=True)
class SatelliteRecord:
    norad_cat_id: str
    object_name: str
    object_id: str | None
    epoch: str | None
    classification_type: str | None
    mean_motion: float | None
    eccentricity: float | None
    inclination: float | None
    ra_of_asc_node: float | None
    arg_of_pericenter: float | None
    mean_anomaly: float | None
    source: str = "CelesTrak"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def collect(*, group: str = "military", timeout: int = 90) -> tuple[bytes, str]:
    normalized = str(group).strip().casefold()
    if normalized not in _ALLOWED_GROUPS:
        raise ValueError("unsupported CelesTrak group")
    response = get(_BASE, query={"GROUP": normalized.upper(), "FORMAT": "JSON"}, timeout=timeout, retries=2, backoff_seconds=2.0)
    return response.payload, response.url


def parse(payload: bytes) -> list[SatelliteRecord]:
    body = json.loads(payload.decode("utf-8"))
    if not isinstance(body, list):
        raise ValueError("CelesTrak OMM JSON payload must be a list")
    rows: list[SatelliteRecord] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        norad = str(item.get("NORAD_CAT_ID") or "").strip()
        name = str(item.get("OBJECT_NAME") or "").strip()
        if not norad or not name:
            continue
        rows.append(SatelliteRecord(
            norad_cat_id=norad,
            object_name=name,
            object_id=_text(item.get("OBJECT_ID")),
            epoch=_text(item.get("EPOCH")),
            classification_type=_text(item.get("CLASSIFICATION_TYPE")),
            mean_motion=_float(item.get("MEAN_MOTION")),
            eccentricity=_float(item.get("ECCENTRICITY")),
            inclination=_float(item.get("INCLINATION")),
            ra_of_asc_node=_float(item.get("RA_OF_ASC_NODE")),
            arg_of_pericenter=_float(item.get("ARG_OF_PERICENTER")),
            mean_anomaly=_float(item.get("MEAN_ANOMALY")),
        ))
    return rows


def _text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _float(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None

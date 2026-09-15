from __future__ import annotations

import json
from dataclasses import dataclass

from ..http import get

_ENDPOINT = "https://overpass-api.de/api/interpreter"
_SELECTORS = {
    "military_base": '["military"="base"]',
    "port": '["harbour"="yes"]',
    "airport": '["aeroway"="aerodrome"]',
    "nuclear_facility": '["power"="plant"]["plant:source"="nuclear"]',
    "power_facility": '["power"="plant"]',
    "refinery": '["industrial"="refinery"]',
    "pipeline": '["man_made"="pipeline"]',
    "telecom": '["man_made"="communications_tower"]',
    "bridge": '["bridge"]["name"]',
}


@dataclass(frozen=True)
class BoundingBox:
    south: float
    west: float
    north: float
    east: float

    def validate(self) -> None:
        if not (-90 <= self.south < self.north <= 90):
            raise ValueError("invalid latitude bounds")
        if not (-180 <= self.west < self.east <= 180):
            raise ValueError("invalid longitude bounds")
        if self.north - self.south > 10 or self.east - self.west > 10:
            raise ValueError("Overpass enrichment bbox may not exceed 10 degrees per axis")
        if (self.north - self.south) * (self.east - self.west) > 50:
            raise ValueError("Overpass enrichment bbox area exceeds bounded policy")

    def text(self) -> str:
        return f"{self.south:.5f},{self.west:.5f},{self.north:.5f},{self.east:.5f}"


def collect(
    *,
    bbox: BoundingBox,
    categories: list[str] | tuple[str, ...],
    timeout: int = 90,
) -> tuple[bytes, str]:
    bbox.validate()
    unique = tuple(dict.fromkeys(str(value).strip() for value in categories if str(value).strip()))
    if not unique or len(unique) > 6:
        raise ValueError("Overpass enrichment requires 1-6 categories per request")
    unknown = [value for value in unique if value not in _SELECTORS]
    if unknown:
        raise ValueError("unsupported Overpass infrastructure categories: " + ", ".join(unknown))
    pieces = []
    for category in unique:
        selector = _SELECTORS[category]
        pieces.append(f'nwr{selector}({bbox.text()});')
    query = "[out:json][timeout:60];(" + "".join(pieces) + ");out center tags qt 5000;"
    response = get(_ENDPOINT, query={"data": query}, timeout=timeout, retries=1, backoff_seconds=2.0)
    return response.payload, response.url


def parse(payload: bytes, *, categories: set[str] | None = None) -> list[dict[str, object]]:
    body = json.loads(payload.decode("utf-8"))
    elements = body.get("elements") or []
    rows: list[dict[str, object]] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags") or {}
        if not isinstance(tags, dict):
            tags = {}
        category = _category(tags)
        if category is None or (categories and category not in categories):
            continue
        lat = _float(element.get("lat")); lon = _float(element.get("lon"))
        center = element.get("center") or {}
        if lat is None and isinstance(center, dict):
            lat = _float(center.get("lat")); lon = _float(center.get("lon"))
        if lat is None or lon is None:
            continue
        name = str(tags.get("name") or tags.get("operator") or f"OSM {element.get('type')} {element.get('id')}").strip()
        osm_type = str(element.get("type") or "unknown")
        osm_id = str(element.get("id") or "")
        rows.append({
            "node_id": f"OSM_{osm_type.upper()}_{osm_id}",
            "name": name,
            "type": category,
            "latitude": lat,
            "longitude": lon,
            "countries": [],
            "themes": ["OpenStreetMap structural context"],
            "source": "OpenStreetMap/Overpass",
            "source_ref": f"{osm_type}/{osm_id}",
            "context_not_evidence": True,
            "structural_context_not_live_status": True,
            "no_vulnerability_inference": True,
        })
    return rows


def _category(tags: dict) -> str | None:
    if tags.get("military") == "base": return "military_base"
    if tags.get("harbour") == "yes": return "port"
    if tags.get("aeroway") == "aerodrome": return "airport"
    if tags.get("power") == "plant" and tags.get("plant:source") == "nuclear": return "nuclear_facility"
    if tags.get("industrial") == "refinery": return "refinery"
    if tags.get("man_made") == "pipeline": return "pipeline"
    if tags.get("man_made") == "communications_tower": return "telecom"
    if tags.get("bridge") and tags.get("name"): return "bridge"
    if tags.get("power") == "plant": return "power_facility"
    return None


def _float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

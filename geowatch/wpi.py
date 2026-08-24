from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from .http import get


_FIELD = {
    "wpi_number": ("wpinumber", "WPI Number", "World Port Index Number"),
    "main_name": ("main_port_", "Main Port Name"),
    "alternate_name": ("alternate_", "Alternate Port Name"),
    "unlocode": ("unlocode", "UN/LOCODE"),
    "country": ("countryCode", "Country Code"),
    "water_body": ("dodwaterbo", "World Water Body"),
    "navarea": ("navarea", "NAVAREA"),
    "latitude": ("Latitude", "latitude"),
    "longitude": ("Longitude", "longitude"),
    "harbor_size": ("harbor_siz", "Harbor Size"),
    "harbor_type": ("harbor_typ", "Harbor Type"),
    "harbor_use": ("harbor_use", "Harbor Use"),
    "container": ("fac_contai", "Facilities - Container"),
    "oil_terminal": ("fac_oilter", "Facilities - Oil Terminal"),
    "lng_terminal": ("fac_lngter", "Facilities - LNG Terminal"),
    "solid_bulk": ("fac_solidb", "Facilities - Solid Bulk"),
    "liquid_bulk": ("fac_liquid", "Facilities - Liquid Bulk"),
    "roro": ("fac_roro", "Facilities - RoRo", "Facilities - Ro-Ro"),
    "rail": ("com_rail", "Communications - Rail"),
    "vts": ("vts", "Vessel Traffic Service"),
    "tss": ("tss", "Traffic Separation Scheme"),
    "channel_depth": ("channel_de", "Channel Depth (m)"),
    "cargo_pier_depth": ("cargo_pier", "Cargo Pier Depth (m)"),
    "oil_terminal_depth": ("oil_termin", "Oil Terminal Depth (m)"),
    "lng_terminal_depth": ("lng_termin", "Liquified Natural Gas Terminal Depth (m)"),
    "max_vessel_length": ("maxvessell", "Maximum Vessel Length (m)"),
    "max_vessel_beam": ("maxvesselb", "Maximum Vessel Beam (m)"),
    "max_vessel_draft": ("maxvesseld", "Maximum Vessel Draft (m)"),
}


def load_registry(path: str | Path = "config/operations/wpi.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def download(*, registry_path: str | Path = "config/operations/wpi.json", timeout: int = 180) -> tuple[list[dict], str]:
    registry = load_registry(registry_path)
    response = get(registry["source_url"], timeout=timeout)
    text = response.payload.decode("utf-8-sig", errors="replace")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))], response.url


def candidate_score(row: dict) -> int:
    """Rank WPI records for structural-enrichment priority only.

    The official WPI CSV uses compact downloaded-field names such as
    ``harbor_siz`` and ``fac_contai``. Plain-language aliases are also accepted for
    tests and historical exports. The score is not a probability of strategic
    importance and never implies current port status.
    """
    score = 0
    harbor = _field_text(row, "harbor_size").casefold()
    if harbor == "large":
        score += 5
    elif harbor == "medium":
        score += 3
    elif harbor == "small":
        score += 1

    for key, weight in (
        ("container", 4),
        ("oil_terminal", 4),
        ("lng_terminal", 5),
        ("solid_bulk", 3),
        ("liquid_bulk", 3),
        ("roro", 2),
        ("rail", 2),
        ("vts", 1),
        ("tss", 1),
    ):
        if _yes(_field_value(row, key)):
            score += weight

    for key, threshold, weight in (
        ("channel_depth", 12.0, 2),
        ("cargo_pier_depth", 12.0, 2),
        ("oil_terminal_depth", 14.0, 2),
        ("lng_terminal_depth", 14.0, 2),
    ):
        if (_float(_field_value(row, key)) or 0.0) >= threshold:
            score += weight
    return score


def to_infrastructure_node(row: dict) -> dict | None:
    name = _field_text(row, "main_name")
    index = _field_text(row, "wpi_number")
    lat = _float(_field_value(row, "latitude"))
    lon = _float(_field_value(row, "longitude"))
    if not name or not index or lat is None or lon is None:
        return None

    facility_labels = {
        "container": "Container",
        "oil_terminal": "Oil Terminal",
        "lng_terminal": "LNG Terminal",
        "solid_bulk": "Solid Bulk",
        "liquid_bulk": "Liquid Bulk",
        "roro": "RoRo",
    }
    facilities = [label for key, label in facility_labels.items() if _yes(_field_value(row, key))]
    return {
        "node_id": f"WPI_{index.replace('.0', '')}",
        "name": name,
        "alternate_name": _field_text(row, "alternate_name") or None,
        "type": "port",
        "country": _field_text(row, "country"),
        "un_locode": _field_text(row, "unlocode") or None,
        "water_body": _field_text(row, "water_body") or None,
        "navarea": _field_text(row, "navarea") or None,
        "latitude": lat,
        "longitude": lon,
        "harbor_size": _field_text(row, "harbor_size") or None,
        "harbor_type": _field_text(row, "harbor_type") or None,
        "harbor_use": _field_text(row, "harbor_use") or None,
        "facilities": facilities,
        "rail_communications": _yes_or_none(_field_value(row, "rail")),
        "vessel_traffic_service": _yes_or_none(_field_value(row, "vts")),
        "traffic_separation_scheme": _yes_or_none(_field_value(row, "tss")),
        "depth_m": {
            "channel": _float(_field_value(row, "channel_depth")),
            "cargo_pier": _float(_field_value(row, "cargo_pier_depth")),
            "oil_terminal": _float(_field_value(row, "oil_terminal_depth")),
            "lng_terminal": _float(_field_value(row, "lng_terminal_depth")),
        },
        "max_vessel_m": {
            "length": _float(_field_value(row, "max_vessel_length")),
            "beam": _float(_field_value(row, "max_vessel_beam")),
            "draft": _float(_field_value(row, "max_vessel_draft")),
        },
        "candidate_score": candidate_score(row),
        "source_ids": ["nga_world_port_index"],
        "source_reference": "UpdatedPub150.csv",
        "structural_context_not_live_status": True,
        "candidate_score_not_criticality_probability": True,
    }


def select_candidates(rows: list[dict], *, limit: int = 300, min_per_water_body: int = 3) -> list[dict]:
    nodes = [node for row in rows if (node := to_infrastructure_node(row)) is not None]
    nodes.sort(key=lambda n: (-int(n["candidate_score"]), str(n.get("water_body") or ""), n["name"]))
    selected: list[dict] = []
    seen: set[str] = set()
    groups: dict[str, list[dict]] = {}
    for node in nodes:
        groups.setdefault(str(node.get("water_body") or "Unknown"), []).append(node)
    for _, group in sorted(groups.items()):
        for node in group[:max(0, min_per_water_body)]:
            if node["node_id"] not in seen:
                selected.append(node)
                seen.add(node["node_id"])
    for node in nodes:
        if len(selected) >= limit:
            break
        if node["node_id"] not in seen:
            selected.append(node)
            seen.add(node["node_id"])
    return selected[:limit]


def _field_value(row: dict, key: str):
    aliases = _FIELD[key]
    for alias in aliases:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    folded = {str(name).casefold(): value for name, value in row.items()}
    for alias in aliases:
        value = folded.get(alias.casefold())
        if value not in (None, ""):
            return value
    return None


def _field_text(row: dict, key: str) -> str:
    return str(_field_value(row, key) or "").strip()


def _yes(value) -> bool:
    return str(value or "").strip().casefold() in {"yes", "y", "true", "1"}


def _yes_or_none(value) -> bool | None:
    text = str(value or "").strip().casefold()
    if text in {"yes", "y", "true", "1"}:
        return True
    if text in {"no", "n", "false", "0"}:
        return False
    return None


def _float(value):
    try:
        text = str(value or "").strip()
        return float(text) if text else None
    except ValueError:
        return None

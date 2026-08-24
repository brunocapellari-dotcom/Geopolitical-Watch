from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from .http import get


def load_registry(path: str | Path = "config/operations/wpi.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def download(*, registry_path: str | Path = "config/operations/wpi.json", timeout: int = 180) -> tuple[list[dict], str]:
    registry = load_registry(registry_path)
    response = get(registry["source_url"], timeout=timeout)
    text = response.payload.decode("utf-8-sig", errors="replace")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))], response.url


def candidate_score(row: dict) -> int:
    """Heuristic ranking for structural-enrichment priority only.

    It is not a probability of strategic importance and does not establish current
    capacity or operational status.
    """
    score = 0
    harbor = _text(row, "Harbor Size").casefold()
    if harbor == "large": score += 5
    elif harbor == "medium": score += 3
    elif harbor == "small": score += 1
    for field, weight in (
        ("Facilities - Container", 4),
        ("Facilities - Oil Terminal", 4),
        ("Facilities - LNG Terminal", 5),
        ("Facilities - Solid Bulk", 3),
        ("Facilities - Liquid Bulk", 3),
        ("Facilities - Ro-Ro", 2),
        ("Communications - Rail", 2),
        ("Vessel Traffic Service", 1),
        ("Traffic Separation Scheme", 1),
    ):
        if _yes(row.get(field)):
            score += weight
    for field, threshold, weight in (
        ("Channel Depth (m)", 12.0, 2),
        ("Cargo Pier Depth (m)", 12.0, 2),
        ("Oil Terminal Depth (m)", 14.0, 2),
        ("Liquified Natural Gas Terminal Depth (m)", 14.0, 2),
    ):
        if (_float(row.get(field)) or 0.0) >= threshold:
            score += weight
    return score


def to_infrastructure_node(row: dict) -> dict | None:
    name = _text(row, "Main Port Name")
    index = _text(row, "World Port Index Number")
    lat = _float(row.get("Latitude")); lon = _float(row.get("Longitude"))
    if not name or not index or lat is None or lon is None:
        return None
    facilities = [field.removeprefix("Facilities - ") for field, value in row.items() if field.startswith("Facilities - ") and _yes(value)]
    return {
        "node_id": f"WPI_{index.replace('.0','')}",
        "name": name,
        "type": "port",
        "country": _text(row, "Country Code"),
        "un_locode": _text(row, "UN/LOCODE") or None,
        "water_body": _text(row, "World Water Body") or None,
        "navarea": _text(row, "NAVAREA") or None,
        "latitude": lat,
        "longitude": lon,
        "harbor_size": _text(row, "Harbor Size") or None,
        "harbor_type": _text(row, "Harbor Type") or None,
        "facilities": facilities,
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
    # First preserve a minimum geographic spread by water body.
    groups: dict[str, list[dict]] = {}
    for node in nodes:
        groups.setdefault(str(node.get("water_body") or "Unknown"), []).append(node)
    for _, group in sorted(groups.items()):
        for node in group[:max(0, min_per_water_body)]:
            if node["node_id"] not in seen:
                selected.append(node); seen.add(node["node_id"])
    for node in nodes:
        if len(selected) >= limit:
            break
        if node["node_id"] not in seen:
            selected.append(node); seen.add(node["node_id"])
    return selected[:limit]


def _text(row: dict, key: str) -> str:
    return str(row.get(key) or "").strip()


def _yes(value) -> bool:
    return str(value or "").strip().casefold() in {"yes", "y", "true", "1"}


def _float(value):
    try:
        text = str(value or "").strip()
        return float(text) if text else None
    except ValueError:
        return None

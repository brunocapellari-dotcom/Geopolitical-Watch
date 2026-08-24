from __future__ import annotations

import re
from typing import Iterable


def build_entity_name_index(*, countries: Iterable[dict] = (), actors: Iterable[dict] = (), graph_nodes: Iterable[dict] = ()) -> dict[str, str]:
    index: dict[str, str] = {}
    for row in countries:
        entity_id = row.get("country_id") or row.get("id")
        for name in (row.get("name"), row.get("official_name")):
            if entity_id and name:
                index[_norm(str(name))] = str(entity_id)
    for row in actors:
        entity_id = row.get("actor_id") or row.get("id")
        if entity_id and row.get("name"):
            index[_norm(str(row["name"]))] = str(entity_id)
        for alias in row.get("aliases", []) or []:
            if entity_id and alias:
                index[_norm(str(alias))] = str(entity_id)
    for row in graph_nodes:
        entity_id = row.get("id") or row.get("node_id")
        if entity_id and row.get("name"):
            index[_norm(str(row["name"]))] = str(entity_id)
    return index


def link_designations(designations: Iterable[dict], *, entity_name_index: dict[str, str]) -> dict:
    """Exact normalized-name linking only; ambiguous/fuzzy matching is deferred to review."""
    linked = []
    unmatched = []
    for designation in designations:
        name = str(designation.get("name") or "").strip()
        entity_id = entity_name_index.get(_norm(name)) if name else None
        row = {
            "designation_id": designation.get("designation_id"),
            "authority": designation.get("authority"),
            "list_name": designation.get("list_name"),
            "effective_date": designation.get("effective_date"),
            "source_url": designation.get("source_url"),
            "name": name,
            "entity_id": entity_id,
            "jurisdiction_semantics_required": True,
            "designation_not_conflict_evidence": True,
        }
        (linked if entity_id else unmatched).append(row)
    return {
        "schema_version": "geowatch-sanctions-graph-links-v1",
        "linked": linked,
        "unmatched": unmatched,
        "linked_count": len(linked),
        "unmatched_count": len(unmatched),
        "matching_method": "exact_normalized_name",
        "fuzzy_matching_requires_review": True,
    }


def _norm(value: str) -> str:
    text = value.casefold().replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())

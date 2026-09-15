from __future__ import annotations

import json
import re
from pathlib import Path

_LAYER_ID = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_ALLOWED_SEMANTICS = {"OBSERVADO", "INFORMADO", "ESTIMADO", "INFERIDO"}
_ALLOWED_ROLES = {"evidence", "context"}
_REQUIRED_IDS = {"conflicts", "infrastructure", "physical", "network", "aircraft", "vessels"}


def load_map_layers(path: str | Path = "config/map_layers.json") -> dict[str, object]:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    if body.get("schema_version") != "geowatch-map-layers-v1":
        raise ValueError("unsupported map layer catalog schema")
    rows = body.get("layers")
    if not isinstance(rows, list) or not rows:
        raise ValueError("map layer catalog requires layers")

    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("map layer must be an object")
        layer_id = str(raw.get("id") or "")
        if not _LAYER_ID.fullmatch(layer_id):
            raise ValueError(f"invalid map layer id: {layer_id!r}")
        if layer_id in seen:
            raise ValueError(f"duplicate map layer id: {layer_id}")
        seen.add(layer_id)

        label = str(raw.get("label") or "").strip()
        source = str(raw.get("source") or "").strip()
        semantics = str(raw.get("semantic_class") or "").strip().upper()
        role = str(raw.get("evidentiary_role") or "").strip().lower()
        note = str(raw.get("note") or "").strip()
        if not label or not source or not note:
            raise ValueError(f"map layer {layer_id} requires label, source and note")
        if semantics not in _ALLOWED_SEMANTICS:
            raise ValueError(f"invalid semantics for {layer_id}: {semantics}")
        if role not in _ALLOWED_ROLES:
            raise ValueError(f"invalid evidentiary role for {layer_id}: {role}")

        refresh = int(raw.get("refresh_seconds") or 0)
        freshness = int(raw.get("freshness_seconds") or 0)
        if refresh < 10 or refresh > 86400:
            raise ValueError(f"refresh_seconds out of bounds for {layer_id}")
        if freshness < refresh or freshness > 31 * 86400:
            raise ValueError(f"freshness_seconds out of bounds for {layer_id}")

        normalized.append(
            {
                "id": layer_id,
                "label": label,
                "source": source,
                "semantic_class": semantics,
                "evidentiary_role": role,
                "default_visible": bool(raw.get("default_visible", False)),
                "refresh_seconds": refresh,
                "freshness_seconds": freshness,
                "note": note,
            }
        )

    missing = _REQUIRED_IDS - seen
    if missing:
        raise ValueError("missing required map layers: " + ", ".join(sorted(missing)))
    return {"schema_version": body["schema_version"], "layers": normalized}


def layer_index(path: str | Path = "config/map_layers.json") -> dict[str, dict[str, object]]:
    return {str(row["id"]): row for row in load_map_layers(path)["layers"]}  # type: ignore[index]

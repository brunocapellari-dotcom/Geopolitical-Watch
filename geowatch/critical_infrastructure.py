from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path


class CriticalInfrastructureGraph:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.nodes = {row["node_id"]: row for row in payload.get("nodes", [])}
        self.edges = list(payload.get("edges", []))
        self.source_status = dict(payload.get("source_status") or {})
        self.taxonomy = list(payload.get("taxonomy") or [])
        self.adj: dict[str, set[str]] = defaultdict(set)
        for edge in self.edges:
            self.adj[edge["from"]].add(edge["to"])
            self.adj[edge["to"]].add(edge["from"])

    @classmethod
    def from_json(
        cls,
        path: str | Path = "config/geopolitics/critical_infrastructure.json",
        supplement_path: str | Path = "config/geopolitics/critical_infrastructure_v011.json",
        wpi_path: str | Path = "generated/wpi/critical_port_candidates.json",
        taxonomy_path: str | Path = "config/geopolitics/infrastructure_taxonomy.json",
    ) -> "CriticalInfrastructureGraph":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        nodes = list(payload.get("nodes", []))
        edges = list(payload.get("edges", []))
        node_ids = {row["node_id"] for row in nodes}
        edge_keys = {(row.get("from"), row.get("to"), row.get("type")) for row in edges}
        source_status: dict[str, object] = {}

        supplement = Path(supplement_path)
        if supplement.exists():
            extra = json.loads(supplement.read_text(encoding="utf-8"))
            for row in extra.get("nodes", []):
                if row["node_id"] not in node_ids:
                    nodes.append(row)
                    node_ids.add(row["node_id"])
            for row in extra.get("edges", []):
                key = (row.get("from"), row.get("to"), row.get("type"))
                if key not in edge_keys:
                    edges.append(row)
                    edge_keys.add(key)

        wpi_file = Path(wpi_path)
        if wpi_file.exists():
            wpi = json.loads(wpi_file.read_text(encoding="utf-8"))
            wpi_rows = list(wpi.get("nodes", []))
            source_status["wpi"] = {
                "status": "persisted",
                "node_count": len(wpi_rows),
                "structural_context_not_live_status": True,
            }
        else:
            from .runtime_wpi import load_runtime_wpi

            wpi_rows, wpi_status = load_runtime_wpi(limit=300)
            source_status["wpi"] = wpi_status

        for raw in wpi_rows:
            row = cls._normalize_wpi_node(raw)
            if row["node_id"] not in node_ids:
                nodes.append(row)
                node_ids.add(row["node_id"])

        taxonomy: list[dict] = []
        taxonomy_file = Path(taxonomy_path)
        if taxonomy_file.exists():
            taxonomy_payload = json.loads(taxonomy_file.read_text(encoding="utf-8"))
            taxonomy = list(taxonomy_payload.get("classes", []))

        return cls({
            **payload,
            "nodes": nodes,
            "edges": edges,
            "source_status": source_status,
            "taxonomy": taxonomy,
        })

    @staticmethod
    def _normalize_wpi_node(row: dict) -> dict:
        country = str(row.get("country") or "").strip()
        return {
            **row,
            "countries": [country] if country else [],
            "themes": list(row.get("facilities") or []),
            "context_not_evidence": True,
            "structural_context_not_live_status": True,
        }

    def node(self, node_id: str) -> dict | None:
        row = self.nodes.get(node_id)
        return {**row, "context_not_evidence": True} if row else None

    def nodes_for_country(self, country_code: str) -> list[dict]:
        code = country_code.upper()
        return [
            {**row, "context_not_evidence": True}
            for row in self.nodes.values()
            if code in [str(value).upper() for value in row.get("countries", [])]
        ]

    def shortest_context_path(self, start: str, end: str) -> list[str]:
        if start == end and start in self.nodes:
            return [start]
        if start not in self.nodes or end not in self.nodes:
            return []
        q = deque([(start, [start])])
        seen = {start}
        while q:
            node, path = q.popleft()
            for nxt in sorted(self.adj.get(node, [])):
                if nxt in seen:
                    continue
                if nxt == end:
                    return path + [nxt]
                seen.add(nxt)
                q.append((nxt, path + [nxt]))
        return []

    def summary(self) -> dict:
        by_type: dict[str, int] = defaultdict(int)
        geocoded = 0
        for row in self.nodes.values():
            by_type[row.get("type", "unknown")] += 1
            if row.get("latitude") is not None and row.get("longitude") is not None:
                geocoded += 1
        required_types = [str(row.get("type")) for row in self.taxonomy if row.get("type")]
        covered_types = sorted(type_name for type_name in required_types if by_type.get(type_name, 0) > 0)
        missing_types = sorted(type_name for type_name in required_types if by_type.get(type_name, 0) == 0)
        return {
            "schema_version": "geowatch-critical-infrastructure-summary-v2",
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "geocoded_node_count": geocoded,
            "by_type": dict(sorted(by_type.items())),
            "required_types": required_types,
            "covered_types": covered_types,
            "missing_types": missing_types,
            "taxonomy_complete": bool(required_types) and not missing_types,
            "source_status": self.source_status,
            "context_not_evidence": True,
            "structural_context_not_live_status": True,
        }

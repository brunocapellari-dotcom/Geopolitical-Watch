from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path


class CriticalInfrastructureGraph:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.nodes = {row["node_id"]: row for row in payload.get("nodes", [])}
        self.edges = list(payload.get("edges", []))
        self.adj: dict[str, set[str]] = defaultdict(set)
        for edge in self.edges:
            self.adj[edge["from"]].add(edge["to"])
            self.adj[edge["to"]].add(edge["from"])

    @classmethod
    def from_json(cls, path: str | Path = "config/geopolitics/critical_infrastructure.json",
                  supplement_path: str | Path = "config/geopolitics/critical_infrastructure_v011.json") -> "CriticalInfrastructureGraph":
        payload=json.loads(Path(path).read_text(encoding="utf-8"))
        supplement=Path(supplement_path)
        if supplement.exists():
            extra=json.loads(supplement.read_text(encoding="utf-8"))
            node_ids={row["node_id"] for row in payload.get("nodes", [])}
            edge_keys={(row.get("from"),row.get("to"),row.get("type")) for row in payload.get("edges", [])}
            payload={**payload,
                "nodes":list(payload.get("nodes", []))+[row for row in extra.get("nodes", []) if row["node_id"] not in node_ids],
                "edges":list(payload.get("edges", []))+[row for row in extra.get("edges", []) if (row.get("from"),row.get("to"),row.get("type")) not in edge_keys]}
        return cls(payload)

    def node(self, node_id: str) -> dict | None:
        row = self.nodes.get(node_id)
        return {**row, "context_not_evidence": True} if row else None

    def nodes_for_country(self, country_code: str) -> list[dict]:
        code = country_code.upper()
        return [{**row, "context_not_evidence": True} for row in self.nodes.values() if code in row.get("countries", [])]

    def shortest_context_path(self, start: str, end: str) -> list[str]:
        if start == end and start in self.nodes:
            return [start]
        if start not in self.nodes or end not in self.nodes:
            return []
        q = deque([(start, [start])]); seen = {start}
        while q:
            node, path = q.popleft()
            for nxt in sorted(self.adj.get(node, [])):
                if nxt in seen:
                    continue
                if nxt == end:
                    return path + [nxt]
                seen.add(nxt); q.append((nxt, path + [nxt]))
        return []

    def summary(self) -> dict:
        by_type: dict[str, int] = defaultdict(int)
        for row in self.nodes.values():
            by_type[row.get("type", "unknown")] += 1
        return {
            "schema_version": "geowatch-critical-infrastructure-summary-v1",
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "by_type": dict(sorted(by_type.items())),
            "context_not_evidence": True,
        }

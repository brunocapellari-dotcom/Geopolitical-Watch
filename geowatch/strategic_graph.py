from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import ConflictEpisode, Entity


class StrategicGraph:
    def __init__(self, profiles: dict, graph: dict) -> None:
        self.profiles_payload = profiles
        self.graph_payload = graph
        self.profiles = {row["country_id"]: row for row in profiles.get("profiles", [])}
        self.nodes = {row["id"]: row for row in graph.get("nodes", [])}
        self.edges = list(graph.get("edges", []))
        self.name_to_country = {row["name"].casefold(): row["country_id"] for row in profiles.get("profiles", [])}

    @classmethod
    def from_files(
        cls,
        profiles_path: str | Path = "config/geopolitics/country_profiles.json",
        graph_path: str | Path = "config/geopolitics/strategic_graph.json",
    ) -> "StrategicGraph":
        profiles = json.loads(Path(profiles_path).read_text(encoding="utf-8"))
        graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
        return cls(profiles, graph)

    def country_profile(self, country: str) -> dict | None:
        if country in self.profiles:
            return self.profiles[country]
        cid = self.name_to_country.get(country.casefold())
        return self.profiles.get(cid) if cid else None

    def edges_for(self, node_ids: Iterable[str]) -> list[dict]:
        ids = set(node_ids)
        return [row for row in self.edges if row.get("source") in ids or row.get("target") in ids]

    def context_for_episode(self, episode: ConflictEpisode, *, entities: Iterable[Entity] = ()) -> dict:
        country_ids = []
        profiles = []
        for country in episode.countries:
            profile = self.country_profile(country)
            if profile:
                country_ids.append(profile["country_id"])
                profiles.append(profile)
        entity_ids = {entity.entity_id for entity in entities}
        related_node_ids = set(country_ids) | entity_ids
        edges = self.edges_for(related_node_ids)
        neighbor_ids = {
            edge["target"] if edge.get("source") in related_node_ids else edge["source"]
            for edge in edges
        }
        neighbors = [self.nodes[node_id] for node_id in sorted(neighbor_ids) if node_id in self.nodes]
        return {
            "schema_version": "geowatch-strategic-graph-context-v1",
            "context_not_evidence": True,
            "country_profiles": profiles,
            "relations": edges,
            "neighbor_nodes": neighbors,
            "methodology_notes": [
                "Strategic graph edges are context objects with explicit sources and validity windows.",
                "Structural exposure edges must be quantified with current data before operational conclusions.",
                "Graph context cannot verify an event, actor attribution or future action.",
            ],
        }

    def export_graph(self) -> dict:
        return {
            "schema_version": self.graph_payload.get("schema_version"),
            "as_of": self.graph_payload.get("as_of"),
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
            "governance": self.graph_payload.get("governance", {}),
        }

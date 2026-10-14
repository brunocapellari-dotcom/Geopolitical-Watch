from __future__ import annotations

import hashlib
from collections.abc import Iterable

from .models import ConflictEpisode, Event

RELATIONSHIP_TYPES = (
    "PRECEDES",
    "FOLLOWS",
    "RESPONSE_TO",
    "RELATED_TO",
    "ESCALATION_OF",
    "DEESCALATION_OF",
    "CONTRADICTS",
    "CONFIRMS",
)

_AUTOMATIC_NON_CAUSAL = frozenset({"PRECEDES", "FOLLOWS", "RELATED_TO"})
_EVIDENCE_REQUIRED = frozenset(set(RELATIONSHIP_TYPES) - _AUTOMATIC_NON_CAUSAL)


def build_event_graph(
    episodes: Iterable[ConflictEpisode],
    events: Iterable[Event],
    *,
    episode_id: str | None = None,
) -> dict[str, object]:
    event_map = {event.event_id: event for event in events}
    selected = [
        episode for episode in episodes
        if episode_id is None or episode.episode_id == episode_id
    ]
    node_ids: set[str] = set()
    links: dict[str, dict[str, object]] = {}

    for episode in selected:
        ordered = sorted(
            (event_map[event_id] for event_id in episode.event_ids if event_id in event_map),
            key=lambda event: (event.reference_at, event.event_id),
        )
        node_ids.update(event.event_id for event in ordered)
        for left, right in zip(ordered, ordered[1:]):
            _add_link(
                links,
                source_event_id=left.event_id,
                target_event_id=right.event_id,
                relationship_type="PRECEDES",
                episode_id=episode.episode_id,
                confidence=1.0,
                derivation_method="episode_timeline_order",
            )
            _add_link(
                links,
                source_event_id=right.event_id,
                target_event_id=left.event_id,
                relationship_type="FOLLOWS",
                episode_id=episode.episode_id,
                confidence=1.0,
                derivation_method="episode_timeline_order",
            )
            _add_link(
                links,
                source_event_id=left.event_id,
                target_event_id=right.event_id,
                relationship_type="RELATED_TO",
                episode_id=episode.episode_id,
                confidence=_related_confidence(episode),
                derivation_method="shared_canonical_episode",
            )

    nodes = [
        {
            "event_id": event.event_id,
            "title": event.title,
            "event_type": event.event_type,
            "reference_at": event.reference_at,
            "country": event.country,
            "region": event.region,
            "location": event.location,
            "verification_level": event.verification_level,
        }
        for event_id in sorted(node_ids)
        if (event := event_map.get(event_id)) is not None
    ]

    return {
        "schema_version": "geowatch-event-graph-v1",
        "nodes": nodes,
        "links": sorted(links.values(), key=lambda row: str(row["relationship_id"])),
        "relationship_types": list(RELATIONSHIP_TYPES),
        "automatic_non_causal_types": sorted(_AUTOMATIC_NON_CAUSAL),
        "evidence_or_review_required_types": sorted(_EVIDENCE_REQUIRED),
        "automatic_causality": False,
    }


def related_event_ids(graph: dict[str, object], event_id: str) -> list[str]:
    related: set[str] = set()
    for link in graph.get("links") or []:
        if not isinstance(link, dict):
            continue
        source = str(link.get("source_event_id") or "")
        target = str(link.get("target_event_id") or "")
        if source == event_id and target:
            related.add(target)
        elif target == event_id and source:
            related.add(source)
    return sorted(related)


def _add_link(
    links: dict[str, dict[str, object]],
    *,
    source_event_id: str,
    target_event_id: str,
    relationship_type: str,
    episode_id: str,
    confidence: float,
    derivation_method: str,
) -> None:
    raw = f"{source_event_id}|{target_event_id}|{relationship_type}|{episode_id}"
    relationship_id = "evrel_" + hashlib.sha256(raw.encode()).hexdigest()[:20]
    links[relationship_id] = {
        "relationship_id": relationship_id,
        "source_event_id": source_event_id,
        "target_event_id": target_event_id,
        "relationship_type": relationship_type,
        "episode_id": episode_id,
        "semantic_class": "derived",
        "confidence": round(max(0.0, min(confidence, 1.0)), 3),
        "derivation_method": derivation_method,
        "causal_claim": False,
        "evidence_required_for_causal_upgrade": True,
    }


def _related_confidence(episode: ConflictEpisode) -> float:
    if episode.evidence_strength is None:
        return 0.5
    return max(0.35, min(0.95, episode.evidence_strength.overall_index / 100.0))


__all__ = ["RELATIONSHIP_TYPES", "build_event_graph", "related_event_ids"]

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

from .core import cluster_events
from .models import Event


def replay_fixture(path: str | Path) -> dict[str, object]:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    events = [Event.from_dict(row) for row in body.get("events", [])]
    clusters = cluster_events(
        events,
        threshold=float(body.get("title_similarity_threshold", 0.78)),
        max_time_delta_hours=float(body.get("cluster_time_hours", 36)),
        max_distance_km=float(body.get("cluster_distance_km", 250)),
    )
    predicted_groups = [sorted(event.event_id for event in cluster.members) for cluster in clusters]
    expected_groups = [sorted(group) for group in body.get("expected_clusters", [])]
    expected_pairs = _pairs(expected_groups)
    predicted_pairs = _pairs(predicted_groups)
    tp = len(expected_pairs & predicted_pairs)
    fp = len(predicted_pairs - expected_pairs)
    fn = len(expected_pairs - predicted_pairs)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {
        "events": len(events),
        "expected_clusters": expected_groups,
        "predicted_clusters": predicted_groups,
        "pairwise_precision": round(precision, 4),
        "pairwise_recall": round(recall, 4),
        "false_positive_pairs": sorted([list(pair) for pair in predicted_pairs - expected_pairs]),
        "missed_pairs": sorted([list(pair) for pair in expected_pairs - predicted_pairs]),
    }


def _pairs(groups: list[list[str]]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for group in groups:
        for left, right in combinations(sorted(group), 2):
            result.add((left, right))
    return result


def replay_episode_fixture(path: str | Path, *, entity_catalog: str | Path = "config/entities.json") -> dict[str, object]:
    from .convergence import converge_events
    from .entities import EntityResolver

    body = json.loads(Path(path).read_text(encoding="utf-8"))
    events = [Event.from_dict(row) for row in body.get("events", [])]
    resolver = EntityResolver.from_json(entity_catalog)
    episodes, claims, evidence, entities, changes = converge_events(events, resolver=resolver)
    predicted_groups = [sorted(episode.event_ids) for episode in episodes]
    expected_groups = [sorted(group) for group in body.get("expected_episodes", [])]
    expected_pairs = _pairs(expected_groups)
    predicted_pairs = _pairs(predicted_groups)
    tp = len(expected_pairs & predicted_pairs)
    fp = len(predicted_pairs - expected_pairs)
    fn = len(expected_pairs - predicted_pairs)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {
        "events": len(events),
        "expected_episodes": len(expected_groups),
        "predicted_episodes": len(predicted_groups),
        "claims": len(claims),
        "evidence": len(evidence),
        "entities": len(entities),
        "changes": len(changes),
        "pairwise_precision": round(precision, 4),
        "pairwise_recall": round(recall, 4),
        "false_positive_pair_count": fp,
        "missed_pair_count": fn,
        "false_positive_pairs": sorted([list(pair) for pair in predicted_pairs - expected_pairs])[:50],
        "missed_pairs": sorted([list(pair) for pair in expected_pairs - predicted_pairs])[:50],
    }

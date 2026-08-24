from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Iterable

from .models import ConflictEpisode


def merge_episodes(
    episodes: Iterable[ConflictEpisode],
    *,
    survivor_id: str | None = None,
    occurred_at: str,
    reason: str,
) -> tuple[ConflictEpisode, list[dict[str, object]]]:
    rows = list(episodes)
    if len(rows) < 2:
        raise ValueError("merge_episodes requires at least two episodes")
    by_id = {row.episode_id: row for row in rows}
    survivor_id = survivor_id or sorted(by_id)[0]
    if survivor_id not in by_id:
        raise ValueError("survivor_id is not one of the supplied episodes")
    survivor = by_id[survivor_id]
    merged_ids = sorted(by_id)

    merged = replace(
        survivor,
        title=survivor.title,
        started_at=min(row.started_at for row in rows),
        last_updated_at=max(row.last_updated_at for row in rows),
        countries=_union(row.countries for row in rows),
        regions=_union(row.regions for row in rows),
        event_ids=_union(row.event_ids for row in rows),
        claim_ids=_union(row.claim_ids for row in rows),
        evidence_ids=_union(row.evidence_ids for row in rows),
        actor_entity_ids=_union(row.actor_entity_ids for row in rows),
        infrastructure_entity_ids=_union(row.infrastructure_entity_ids for row in rows),
        other_entity_ids=_union(row.other_entity_ids for row in rows),
        change_flags=tuple(sorted(set(survivor.change_flags) | {"episode_merge_requires_recompute"})),
        evidence_strength=None,
        version=max(row.version for row in rows) + 1,
    )
    lineage = [{
        "episode_id": survivor_id,
        "at": occurred_at,
        "change_type": "episode_merge",
        "survivor_episode_id": survivor_id,
        "merged_episode_ids": merged_ids,
        "reason": reason,
        "requires_recompute": ["claims_episode_ids", "evidence_strength", "episode_state"],
    }]
    for row in rows:
        if row.episode_id == survivor_id:
            continue
        lineage.append({
            "episode_id": row.episode_id,
            "at": occurred_at,
            "change_type": "episode_merged_into",
            "target_episode_id": survivor_id,
            "reason": reason,
        })
    return merged, lineage


def build_split_plan(
    episode: ConflictEpisode,
    *,
    event_groups: Iterable[Iterable[str]],
    occurred_at: str,
    reason: str,
) -> dict:
    """Build an auditable split plan without silently reassigning claims/evidence.

    A split must be reviewed because claims/evidence can span multiple event groups.
    The plan creates deterministic candidate episode IDs and explicitly records that
    claims, evidence strength and state require recomputation before persistence.
    """
    groups = [tuple(sorted(set(group))) for group in event_groups]
    groups = [group for group in groups if group]
    if len(groups) < 2:
        raise ValueError("split requires at least two non-empty event groups")
    known = set(episode.event_ids)
    assigned = set().union(*(set(group) for group in groups))
    if not assigned <= known:
        raise ValueError("split plan contains event IDs not present in episode")
    if len(assigned) != sum(len(group) for group in groups):
        raise ValueError("event groups overlap")

    children = []
    for index, group in enumerate(groups, 1):
        fingerprint = episode.episode_id + "|" + "|".join(group)
        child_id = "ep_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
        children.append({
            "candidate_episode_id": child_id,
            "source_episode_id": episode.episode_id,
            "group_index": index,
            "event_ids": list(group),
            "requires_recompute": [
                "title", "countries", "regions", "claims", "evidence",
                "entities", "state", "evidence_strength", "strategic_context"
            ],
        })
    unassigned = sorted(known - assigned)
    return {
        "schema_version": "geowatch-episode-split-plan-v1",
        "episode_id": episode.episode_id,
        "occurred_at": occurred_at,
        "reason": reason,
        "children": children,
        "unassigned_event_ids": unassigned,
        "safe_to_apply": not unassigned,
        "lineage_change": {
            "episode_id": episode.episode_id,
            "at": occurred_at,
            "change_type": "episode_split_planned",
            "candidate_child_ids": [row["candidate_episode_id"] for row in children],
            "reason": reason,
        },
    }


def _union(groups: Iterable[Iterable[str]]) -> tuple[str, ...]:
    values: set[str] = set()
    for group in groups:
        values.update(group)
    return tuple(sorted(values))

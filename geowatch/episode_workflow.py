from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .claims import extract_claim, reconcile_claims
from .convergence import calculate_evidence_strength, converge_events, derive_episode_state
from .entities import EntityResolver
from .episode_ops import build_split_plan, merge_episodes
from .models import Claim, ConflictEpisode
from .strategic_state import list_operations, record_operation


def apply_merge(store, episode_ids: list[str], *, survivor_id: str | None = None, reason: str,
                occurred_at: str | None = None) -> dict:
    occurred_at = occurred_at or datetime.now(timezone.utc).isoformat()
    episodes = [store.get_episode(eid) for eid in episode_ids]
    if any(row is None for row in episodes):
        missing = [eid for eid, row in zip(episode_ids, episodes) if row is None]
        raise KeyError(f"missing episodes: {missing}")
    rows = [row for row in episodes if row is not None]
    before_claims = [claim for eid in episode_ids for claim in store.load_claims(episode_id=eid)]
    before = {"episodes": [row.to_dict() for row in rows], "claims": [row.to_dict() for row in before_claims]}

    merged, lineage = merge_episodes(rows, survivor_id=survivor_id, occurred_at=occurred_at, reason=reason)
    reassigned_claims = [replace(claim, episode_id=merged.episode_id) for claim in before_claims]
    reassigned_claims = reconcile_claims(reassigned_claims)
    events = store.load_events_by_ids(merged.event_ids)
    evidence = store.load_evidence()
    entities = store.load_entities()
    merged = replace(
        merged,
        claim_ids=tuple(sorted(claim.claim_id for claim in reassigned_claims)),
        state=derive_episode_state(merged, reassigned_claims, events),
    )
    merged = replace(
        merged,
        evidence_strength=calculate_evidence_strength(merged, reassigned_claims, events, evidence, entities),
        change_flags=tuple(sorted(set(merged.change_flags) | {"episode_merge_applied"})),
    )
    archived = [
        replace(row, state="closed", change_flags=tuple(sorted(set(row.change_flags) | {f"merged_into:{merged.episode_id}"})), version=row.version + 1)
        for row in rows if row.episode_id != merged.episode_id
    ]
    store.upsert_claims(reassigned_claims)
    store.upsert_episodes([merged, *archived])
    store.record_changes(lineage)
    after = {"survivor": merged.to_dict(), "archived": [row.to_dict() for row in archived], "claims": [row.to_dict() for row in reassigned_claims]}
    operation = record_operation(
        store, operation_type="merge", source_episode_ids=episode_ids,
        target_episode_ids=[merged.episode_id], reason=reason, before=before, after=after, occurred_at=occurred_at,
    )
    return {"operation": operation, "episode": merged.to_dict(), "lineage": lineage}


def apply_split(store, episode_id: str, *, event_groups: list[list[str]], reason: str,
                occurred_at: str | None = None, resolver: EntityResolver | None = None) -> dict:
    occurred_at = occurred_at or datetime.now(timezone.utc).isoformat()
    episode = store.get_episode(episode_id)
    if episode is None:
        raise KeyError(episode_id)
    plan = build_split_plan(episode, event_groups=event_groups, occurred_at=occurred_at, reason=reason)
    if not plan["safe_to_apply"]:
        raise ValueError("split plan leaves unassigned events")
    resolver = resolver or EntityResolver.from_json("config/entities.json")
    before = {"episode": episode.to_dict(), "claims": [row.to_dict() for row in store.load_claims(episode_id=episode_id)]}
    children: list[ConflictEpisode] = []
    all_claims: list[Claim] = []
    all_evidence = []
    all_entities = []
    lineage = [plan["lineage_change"]]

    for child_plan in plan["children"]:
        child_id = child_plan["candidate_episode_id"]
        events = store.load_events_by_ids(child_plan["event_ids"])
        generated, _, _, _, _ = converge_events(events, resolver=resolver)
        if len(generated) != 1:
            raise ValueError("split group does not converge to exactly one child episode")
        base = generated[0]
        child_claims = []
        child_evidence = []
        for event in events:
            claim, evidence, entities = extract_claim(event, child_id, resolver)
            child_claims.append(claim)
            child_evidence.append(evidence)
            all_entities.extend(entities)
        child_claims = reconcile_claims(child_claims)
        child = replace(
            base,
            episode_id=child_id,
            claim_ids=tuple(sorted(row.claim_id for row in child_claims)),
            evidence_ids=tuple(sorted(row.evidence_id for row in child_evidence)),
            change_flags=("episode_split_child",),
            version=1,
        )
        child = replace(child, state=derive_episode_state(child, child_claims, events))
        child = replace(child, evidence_strength=calculate_evidence_strength(child, child_claims, events, child_evidence, resolver.entities.values()))
        children.append(child)
        all_claims.extend(child_claims)
        all_evidence.extend(child_evidence)
        lineage.append({"episode_id": child_id, "at": occurred_at, "change_type": "episode_split_created", "source_episode_id": episode_id})

    original_closed = replace(
        episode, state="closed", version=episode.version + 1,
        change_flags=tuple(sorted(set(episode.change_flags) | {"episode_split_applied", "split_into:" + ",".join(row.episode_id for row in children)})),
    )
    store.upsert_entities(all_entities)
    store.upsert_evidence(all_evidence)
    store.upsert_claims(all_claims)
    store.upsert_episodes([original_closed, *children])
    store.record_changes(lineage)
    after = {"original": original_closed.to_dict(), "children": [row.to_dict() for row in children], "claims": [row.to_dict() for row in all_claims]}
    operation = record_operation(
        store, operation_type="split", source_episode_ids=[episode_id], target_episode_ids=[row.episode_id for row in children],
        reason=reason, before=before, after=after, occurred_at=occurred_at,
    )
    return {"operation": operation, "children": [row.to_dict() for row in children], "lineage": lineage}


def revert_operation(store, operation_id: str, *, reason: str, occurred_at: str | None = None) -> dict:
    occurred_at = occurred_at or datetime.now(timezone.utc).isoformat()
    operation = next((row for row in list_operations(store, limit=5000) if row["operation_id"] == operation_id), None)
    if operation is None:
        raise KeyError(operation_id)
    before = operation.get("before") or {}
    restored = []
    restored_claims = []
    if operation["operation_type"] == "merge":
        restored = [ConflictEpisode.from_dict(row) for row in before.get("episodes", [])]
        restored_claims = [Claim.from_dict(row) for row in before.get("claims", [])]
        store.upsert_claims(restored_claims)
        store.upsert_episodes(restored)
        target = operation.get("target_episode_ids", [])
        for eid in target:
            if eid not in {row.episode_id for row in restored}:
                current = store.get_episode(eid)
                if current:
                    store.upsert_episodes([replace(current, state="closed", change_flags=tuple(sorted(set(current.change_flags) | {"operation_reverted"})), version=current.version + 1)])
    elif operation["operation_type"] == "split":
        source_row = before.get("episode")
        if source_row:
            source = ConflictEpisode.from_dict(source_row)
            restored = [source]
            store.upsert_episodes([source])
        restored_claims = [Claim.from_dict(row) for row in before.get("claims", [])]
        if restored_claims:
            store.upsert_claims(restored_claims)
        for child_id in operation.get("target_episode_ids", []):
            child = store.get_episode(child_id)
            if child:
                store.upsert_episodes([replace(child, state="closed", change_flags=tuple(sorted(set(child.change_flags) | {"split_reverted"})), version=child.version + 1)])
    else:
        raise ValueError(f"unsupported operation type: {operation['operation_type']}")

    lineage = [{
        "episode_id": eid, "at": occurred_at, "change_type": "episode_operation_reverted",
        "operation_id": operation_id, "reason": reason,
    } for eid in operation.get("source_episode_ids", [])]
    store.record_changes(lineage)
    revert = record_operation(
        store, operation_type="revert", source_episode_ids=operation.get("target_episode_ids", []),
        target_episode_ids=operation.get("source_episode_ids", []), reason=reason,
        before=operation.get("after"), after={"restored": [row.to_dict() for row in restored], "claims": [row.to_dict() for row in restored_claims]},
        occurred_at=occurred_at, metadata={"reverts_operation_id": operation_id},
    )
    return {"operation": revert, "lineage": lineage}

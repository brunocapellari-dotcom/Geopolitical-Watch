from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import Iterable

from .models import Claim, ConflictEpisode, Event, EvidenceRef
from .validation import episode_quality_flags


@dataclass(frozen=True)
class ReviewItem:
    review_id: str
    episode_id: str
    priority: str
    reasons: tuple[str, ...]
    suggested_actions: tuple[str, ...]
    status: str = "pending"

    def to_dict(self) -> dict:
        return asdict(self)


def build_review_queue(
    episodes: Iterable[ConflictEpisode],
    *,
    claims: Iterable[Claim] = (),
    events: Iterable[Event] = (),
    evidence: Iterable[EvidenceRef] = (),
    limit: int = 200,
) -> list[ReviewItem]:
    claim_map: dict[str, list[Claim]] = {}
    for claim in claims:
        claim_map.setdefault(claim.episode_id, []).append(claim)
    event_map = {event.event_id: event for event in events}
    evidence_map = {row.evidence_id: row for row in evidence}

    rows: list[ReviewItem] = []
    for episode in episodes:
        ep_events = [event_map[eid] for eid in episode.event_ids if eid in event_map]
        ep_evidence = [evidence_map[eid] for eid in episode.evidence_ids if eid in evidence_map]
        reasons = episode_quality_flags(episode, events=ep_events, evidence=ep_evidence)
        ep_claims = claim_map.get(episode.episode_id, [])
        if any(claim.status == "disputed" for claim in ep_claims) and "contradiction_present" not in reasons:
            reasons.append("disputed_claim")
        if any(claim.status == "retracted" for claim in ep_claims) and "retraction_present" not in reasons:
            reasons.append("retracted_claim")
        if not reasons:
            continue

        priority = _priority(reasons)
        actions = _suggested_actions(reasons)
        fingerprint = episode.episode_id + "|" + "|".join(sorted(reasons))
        review_id = "rev_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
        rows.append(ReviewItem(
            review_id=review_id,
            episode_id=episode.episode_id,
            priority=priority,
            reasons=tuple(sorted(set(reasons))),
            suggested_actions=actions,
        ))

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows.sort(key=lambda item: (order[item.priority], item.episode_id))
    return rows[: max(1, limit)]


def _priority(reasons: list[str]) -> str:
    values = set(reasons)
    if values & {"retraction_present", "contradiction_present", "disputed_claim", "retracted_claim"}:
        return "critical"
    if values & {"geography_unresolved", "single_provider_or_unresolved_independence"}:
        return "high"
    if "low_evidence_strength" in values:
        return "medium"
    return "low"


def _suggested_actions(reasons: list[str]) -> tuple[str, ...]:
    values = set(reasons)
    actions: list[str] = []
    if values & {"contradiction_present", "disputed_claim", "retraction_present", "retracted_claim"}:
        actions += ["inspect_claim_evidence_lineage", "seek_independent_corroboration"]
    if "geography_unresolved" in values:
        actions += ["resolve_geography", "review_entity_aliases"]
    if "single_provider_or_unresolved_independence" in values:
        actions += ["check_provider_independence", "seek_second_provider"]
    if "low_evidence_strength" in values:
        actions += ["review_evidence_strength_components"]
    if "emerging_episode" in values:
        actions += ["monitor_for_episode_attachment_or_split"]
    return tuple(dict.fromkeys(actions))

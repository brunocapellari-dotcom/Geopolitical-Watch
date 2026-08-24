from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .strategic_state import record_knowledge_proposal


def propose_from_review_decisions(store, decisions: Iterable[dict], *, min_support: int = 2) -> list[dict]:
    """Turn repeated reviewed corrections into proposals, never automatic knowledge changes."""
    if min_support < 1:
        raise ValueError("min_support must be >= 1")
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for decision in decisions:
        metadata = decision.get("metadata") or {}
        candidate = metadata.get("knowledge_candidate")
        if not isinstance(candidate, dict):
            continue
        proposal_type = str(candidate.get("proposal_type") or "review_pattern")
        subject_id = str(candidate.get("subject_id") or decision.get("episode_id") or "unknown")
        grouped[(proposal_type, subject_id)].append(decision)

    proposals = []
    for (proposal_type, subject_id), rows in grouped.items():
        if len(rows) < min_support:
            continue
        candidate_payloads = [(row.get("metadata") or {}).get("knowledge_candidate") for row in rows]
        proposal = record_knowledge_proposal(
            store,
            proposal_type=proposal_type,
            subject_id=subject_id,
            rationale=f"Repeated analyst-reviewed pattern observed in {len(rows)} decisions; human approval required before knowledge mutation.",
            source_decision_ids=[str(row["decision_id"]) for row in rows],
            payload={"candidates": candidate_payloads, "support_count": len(rows), "auto_apply": False},
        )
        proposals.append(proposal)
    return proposals


def learning_policy() -> dict:
    return {
        "schema_version": "geowatch-learning-policy-v1",
        "auto_mutate_knowledge": False,
        "auto_mutate_evidence": False,
        "requires_reviewed_decisions": True,
        "requires_source_provenance_before_acceptance": True,
        "requires_versioned_change": True,
        "allowed_outputs": ["knowledge_proposal", "alias_proposal", "source_quality_proposal", "methodology_proposal"],
        "prohibited_outputs": ["automatic_fact_rewrite", "automatic_actor_attribution", "automatic_probability_relabeling"],
    }

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .models import ConflictEpisode
from .verdict import VerdictResult


@dataclass(frozen=True)
class AlertPolicy:
    policy_id: str
    severity: str
    states: tuple[str, ...] = ()
    change_types: tuple[str, ...] = ()
    required_flags: tuple[str, ...] = ()
    min_strength: int = 0
    infrastructure_required: bool = False
    countries: tuple[str, ...] = ()
    allowed_verdicts: tuple[str, ...] = ()
    min_verdict_confidence: int = 0
    enabled: bool = True

    @classmethod
    def from_dict(cls, row: dict) -> "AlertPolicy":
        return cls(
            policy_id=str(row["policy_id"]), severity=str(row.get("severity", "medium")),
            states=tuple(row.get("states") or ()), change_types=tuple(row.get("change_types") or ()),
            required_flags=tuple(row.get("required_flags") or ()), min_strength=int(row.get("min_strength", 0)),
            infrastructure_required=bool(row.get("infrastructure_required", False)),
            countries=tuple(row.get("countries") or ()),
            allowed_verdicts=tuple(str(value) for value in (row.get("allowed_verdicts") or ())),
            min_verdict_confidence=max(0, min(int(row.get("min_verdict_confidence", 0)), 100)),
            enabled=bool(row.get("enabled", True)),
        )


def load_policies(path: str | Path = "config/alerts.json") -> list[AlertPolicy]:
    p = Path(path)
    if not p.exists():
        return []
    body = json.loads(p.read_text(encoding="utf-8"))
    return [AlertPolicy.from_dict(row) for row in body.get("policies", [])]


def evaluate_alerts(
    episodes: Iterable[ConflictEpisode],
    changes: Iterable[dict[str, object]],
    policies: Iterable[AlertPolicy],
    *,
    created_at: str | None = None,
    claim_verdicts: Mapping[str, VerdictResult] | None = None,
) -> list[dict[str, object]]:
    created = created_at or datetime.now(timezone.utc).isoformat()
    verdict_map = claim_verdicts or {}
    change_map: dict[str, set[str]] = {}
    for change in changes:
        episode_id = str(change.get("episode_id") or "")
        change_type = str(change.get("change_type") or "")
        if episode_id and change_type:
            change_map.setdefault(episode_id, set()).add(change_type)
    alerts: list[dict[str, object]] = []
    for episode in episodes:
        strength = episode.evidence_strength.overall_index if episode.evidence_strength else 0
        episode_changes = change_map.get(episode.episode_id, set())
        episode_verdicts = [verdict_map[cid] for cid in episode.claim_ids if cid in verdict_map]
        for policy in policies:
            if not _matches(policy, episode, strength, episode_changes, episode_verdicts):
                continue
            fingerprint = "|".join([policy.policy_id, episode.episode_id, str(episode.version), episode.state, ",".join(sorted(episode_changes)), ",".join(sorted(episode.change_flags))])
            relevant_verdicts = _relevant_verdicts(policy, episode_verdicts)
            alerts.append({
                "schema_version": "geowatch-alert-v2",
                "alert_id": "alt_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20],
                "policy_id": policy.policy_id, "episode_id": episode.episode_id, "created_at": created,
                "severity": policy.severity, "state": episode.state, "title": episode.title,
                "countries": list(episode.countries), "evidence_strength_index": strength,
                "change_types": sorted(episode_changes), "change_flags": list(episode.change_flags),
                "infrastructure_entity_ids": list(episode.infrastructure_entity_ids),
                "claim_verdicts": [row.to_dict() for row in relevant_verdicts[:10]],
                "reason": _reason(policy, episode, strength, episode_changes, relevant_verdicts),
            })
    return alerts


def enqueue_alerts(store, alerts: Iterable[dict[str, object]]) -> int:
    return sum(1 if store.enqueue_alert(alert) else 0 for alert in alerts)


def _matches(
    policy: AlertPolicy,
    episode: ConflictEpisode,
    strength: int,
    changes: set[str],
    verdicts: list[VerdictResult],
) -> bool:
    if not policy.enabled or (policy.states and episode.state not in policy.states) or strength < policy.min_strength:
        return False
    if policy.infrastructure_required and not episode.infrastructure_entity_ids:
        return False
    if policy.countries and not (set(policy.countries) & set(episode.countries)):
        return False
    if policy.change_types and not (set(policy.change_types) & changes):
        return False
    if policy.required_flags and not (set(policy.required_flags) & set(episode.change_flags)):
        return False
    if policy.allowed_verdicts or policy.min_verdict_confidence:
        if not any(
            (not policy.allowed_verdicts or verdict.verdict in policy.allowed_verdicts)
            and verdict.confidence >= policy.min_verdict_confidence
            for verdict in verdicts
        ):
            return False
    return True


def _relevant_verdicts(policy: AlertPolicy, verdicts: list[VerdictResult]) -> list[VerdictResult]:
    rows = [
        verdict for verdict in verdicts
        if (not policy.allowed_verdicts or verdict.verdict in policy.allowed_verdicts)
        and verdict.confidence >= policy.min_verdict_confidence
    ]
    return sorted(rows, key=lambda row: row.confidence, reverse=True)


def _reason(
    policy: AlertPolicy,
    episode: ConflictEpisode,
    strength: int,
    changes: set[str],
    verdicts: list[VerdictResult],
) -> str:
    parts = [f"policy={policy.policy_id}", f"state={episode.state}", f"evidence_strength={strength}"]
    if changes:
        parts.append("changes=" + ",".join(sorted(changes)))
    if episode.change_flags:
        parts.append("flags=" + ",".join(sorted(episode.change_flags)))
    if episode.infrastructure_entity_ids:
        parts.append(f"infrastructure_entities={len(episode.infrastructure_entity_ids)}")
    if verdicts:
        best = verdicts[0]
        parts.append(f"verdict={best.verdict}")
        parts.append(f"verdict_confidence={best.confidence}")
    return "; ".join(parts)

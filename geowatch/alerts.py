from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import ConflictEpisode


@dataclass(frozen=True)
class AlertPolicy:
    policy_id: str
    severity: str
    states: tuple[str, ...] = ()
    change_types: tuple[str, ...] = ()
    min_strength: int = 0
    infrastructure_required: bool = False
    countries: tuple[str, ...] = ()
    enabled: bool = True

    @classmethod
    def from_dict(cls, row: dict) -> "AlertPolicy":
        return cls(
            policy_id=str(row["policy_id"]),
            severity=str(row.get("severity", "medium")),
            states=tuple(row.get("states") or ()),
            change_types=tuple(row.get("change_types") or ()),
            min_strength=int(row.get("min_strength", 0)),
            infrastructure_required=bool(row.get("infrastructure_required", False)),
            countries=tuple(row.get("countries") or ()),
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
) -> list[dict[str, object]]:
    created = created_at or datetime.now(timezone.utc).isoformat()
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
        for policy in policies:
            if not _matches(policy, episode, strength, episode_changes):
                continue
            fingerprint = "|".join([
                policy.policy_id,
                episode.episode_id,
                str(episode.version),
                episode.state,
                ",".join(sorted(episode_changes)),
            ])
            alert_id = "alt_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
            alerts.append({
                "schema_version": "geowatch-alert-v1",
                "alert_id": alert_id,
                "policy_id": policy.policy_id,
                "episode_id": episode.episode_id,
                "created_at": created,
                "severity": policy.severity,
                "state": episode.state,
                "title": episode.title,
                "countries": list(episode.countries),
                "evidence_strength_index": strength,
                "change_types": sorted(episode_changes),
                "infrastructure_entity_ids": list(episode.infrastructure_entity_ids),
                "reason": _reason(policy, episode, strength, episode_changes),
            })
    return alerts


def enqueue_alerts(store, alerts: Iterable[dict[str, object]]) -> int:
    inserted = 0
    for alert in alerts:
        inserted += 1 if store.enqueue_alert(alert) else 0
    return inserted


def _matches(policy: AlertPolicy, episode: ConflictEpisode, strength: int, changes: set[str]) -> bool:
    if not policy.enabled:
        return False
    if policy.states and episode.state not in policy.states:
        return False
    if strength < policy.min_strength:
        return False
    if policy.infrastructure_required and not episode.infrastructure_entity_ids:
        return False
    if policy.countries and not (set(policy.countries) & set(episode.countries)):
        return False
    if policy.change_types and not (set(policy.change_types) & changes):
        return False
    return True


def _reason(policy: AlertPolicy, episode: ConflictEpisode, strength: int, changes: set[str]) -> str:
    parts = [f"policy={policy.policy_id}", f"state={episode.state}", f"evidence_strength={strength}"]
    if changes:
        parts.append("changes=" + ",".join(sorted(changes)))
    if episode.infrastructure_entity_ids:
        parts.append(f"infrastructure_entities={len(episode.infrastructure_entity_ids)}")
    return "; ".join(parts)

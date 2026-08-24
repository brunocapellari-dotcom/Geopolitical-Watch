from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable

from .geopolitics import GeopoliticalKnowledge
from .models import Claim, ConflictEpisode, Entity, Event, EvidenceRef


def build_episode_report(
    episodes: Iterable[ConflictEpisode],
    *,
    claims: Iterable[Claim] = (),
    evidence: Iterable[EvidenceRef] = (),
    entities: Iterable[Entity] = (),
    events: Iterable[Event] = (),
    generated_at: str | None = None,
    max_episodes: int = 50,
    geopolitical_knowledge: GeopoliticalKnowledge | None = None,
) -> dict:
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    claim_map: dict[str, Claim] = {claim.claim_id: claim for claim in claims}
    evidence_map: dict[str, EvidenceRef] = {row.evidence_id: row for row in evidence}
    entity_map: dict[str, Entity] = {entity.entity_id: entity for entity in entities}
    event_map: dict[str, Event] = {event.event_id: event for event in events}
    if geopolitical_knowledge is None:
        try:
            geopolitical_knowledge = GeopoliticalKnowledge.from_files()
        except (FileNotFoundError, json_error_types()):
            geopolitical_knowledge = None

    ranked = sorted(
        episodes,
        key=lambda ep: ((ep.evidence_strength.overall_index if ep.evidence_strength else 0), ep.last_updated_at),
        reverse=True,
    )[:max_episodes]
    rows: list[dict[str, object]] = []
    for episode in ranked:
        ep_claims = [claim_map[cid] for cid in episode.claim_ids if cid in claim_map]
        ep_evidence = [evidence_map[eid] for eid in episode.evidence_ids if eid in evidence_map]
        ep_events = [event_map[eid] for eid in episode.event_ids if eid in event_map]
        entity_ids = set(episode.actor_entity_ids) | set(episode.infrastructure_entity_ids) | set(episode.other_entity_ids)
        ep_entities = [entity_map[eid] for eid in entity_ids if eid in entity_map]
        strategic_context = (
            geopolitical_knowledge.context_for_episode(
                episode, claims=ep_claims, entities=ep_entities, events=ep_events
            )
            if geopolitical_knowledge is not None
            else {"context_not_evidence": True, "status": "knowledge_layer_unavailable"}
        )
        rows.append({
            **episode.to_dict(),
            "claims": [claim.to_dict() for claim in sorted(ep_claims, key=lambda c: c.last_seen_at, reverse=True)],
            "evidence": [row.to_dict() for row in sorted(ep_evidence, key=lambda e: e.observed_at, reverse=True)],
            "entities": [entity.to_dict() for entity in ep_entities],
            "recent_events": [event.to_dict() for event in sorted(ep_events, key=lambda e: e.reference_at, reverse=True)[:20]],
            "strategic_context": strategic_context,
            "methodology_notes": [
                "Episode state is a deterministic analytical state derived from preserved claims/events; it is not an official conflict classification.",
                "Evidence strength is a decomposed heuristic index and must not be interpreted as probability that a claim is true.",
                "Contradictions, corrections and retractions remain in the episode lineage instead of being overwritten.",
                "Geopolitical strategic context is non-evidentiary and cannot verify an event, claim or attribution.",
            ],
        })
    report_id = "epr_" + hashlib.sha256((generated + "|" + "|".join(row["episode_id"] for row in rows)).encode()).hexdigest()[:20]
    return {
        "schema_version": "geowatch-episode-report-v1",
        "report_id": report_id,
        "report_type": "episode_situational",
        "generated_at": generated,
        "episode_count": len(rows),
        "episodes": rows,
    }


def build_episode_feed(report: dict) -> dict:
    return {
        "schema_version": "geowatch-feed-v2",
        "provider": "Geopolitical Watch",
        "generated_at": report["generated_at"],
        "report_id": report["report_id"],
        "episodes": report.get("episodes", []),
        "compatibility": {
            "event_feed": "geowatch-feed-v1 remains available at /v1/feed",
            "semantics": "v2 episodes aggregate events/claims/evidence, preserve lineage, and may include non-evidentiary geopolitical context",
        },
    }


def render_episode_markdown(report: dict) -> str:
    lines = [
        "# Geopolitical Watch — Episode Report", "",
        f"Generated: {report['generated_at']}",
        f"Episodes: {report['episode_count']}", "",
    ]
    for i, episode in enumerate(report.get("episodes", []), 1):
        strength = (episode.get("evidence_strength") or {}).get("overall_index")
        lines += [
            f"## {i}. {episode['title']}", "",
            f"**Episode:** `{episode['episode_id']}`  ",
            f"**State:** {episode['state']}  ",
            f"**Started:** {episode['started_at']}  ",
            f"**Last update:** {episode['last_updated_at']}  ",
            f"**Evidence strength index:** {strength if strength is not None else 'n/a'} (not probability)  ",
        ]
        if episode.get("countries"):
            lines.append(f"**Countries:** {', '.join(episode['countries'])}  ")
        entities = episode.get("entities", [])
        if entities:
            lines += ["", "### Entities", ""]
            for entity in entities[:15]:
                lines.append(f"- {entity['canonical_name']} ({entity['entity_type']})")
        claims = episode.get("claims", [])
        if claims:
            lines += ["", "### Claims", ""]
            for claim in claims[:20]:
                lines.append(f"- [{claim['status']}] {claim['statement']} — {claim['claim_type']}")
        context = episode.get("strategic_context") or {}
        concepts = context.get("matched_concepts") or []
        if concepts:
            lines += ["", "### Strategic context (not evidence)", ""]
            lines.append("**Concepts:** " + ", ".join(item["name"] for item in concepts[:8]))
            lenses = context.get("theoretical_lenses") or []
            if lenses:
                lines.append("**Lenses:** " + ", ".join(item["name"] for item in lenses[:6]))
            analogies = context.get("historical_analogies") or []
            if analogies:
                lines.append("**Historical comparison prompts:** " + ", ".join(item["id"] for item in analogies[:3]))
            questions = context.get("analytical_questions") or []
            if questions:
                lines += ["", "Analytical questions:"]
                for question in questions[:6]:
                    lines.append(f"- {question}")
        recent = episode.get("recent_events", [])
        if recent:
            lines += ["", "### Recent evidence/events", ""]
            for event in recent[:10]:
                link = f" — {event['source_url']}" if event.get("source_url") else ""
                lines.append(f"- {event.get('publisher') or event['source_id']}: {event['title']}{link}")
        if episode.get("change_flags"):
            lines += ["", "### Change flags", ""]
            for flag in episode["change_flags"]:
                lines.append(f"- {flag}")
        lines.append("")
    return "\n".join(lines) + "\n"


def json_error_types():
    import json
    return json.JSONDecodeError

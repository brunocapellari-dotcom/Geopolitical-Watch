from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable

from .claims import extract_claim, infer_claim_type, reconcile_claims
from .core import title_similarity
from .entities import EntityResolver, split_entities
from .history import parse_utc
from .models import Claim, ConflictEpisode, Entity, Event, EvidenceRef, EvidenceStrength
from .source_independence import independent_event_source_count, independent_source_count

_ESCALATION_CLAIMS = {"attack", "ceasefire_collapse", "mobilization", "territorial_change"}
_DEESCALATION_CLAIMS = {"ceasefire", "infrastructure_restoration"}
_CONTEXT_ONLY_SOURCE_IDS = {"gdacs_context"}


def converge_events(
    events: Iterable[Event],
    *,
    existing_episodes: Iterable[ConflictEpisode] = (),
    existing_claims: Iterable[Claim] = (),
    existing_evidence: Iterable[EvidenceRef] = (),
    resolver: EntityResolver | None = None,
    attach_threshold: float = 0.33,
    now: datetime | None = None,
) -> tuple[list[ConflictEpisode], list[Claim], list[EvidenceRef], list[Entity], list[dict[str, object]]]:
    resolver = resolver or EntityResolver()
    now = now or datetime.now(timezone.utc)
    event_rows = list(events)
    episodes: dict[str, ConflictEpisode] = {ep.episode_id: ep for ep in existing_episodes}
    claims: dict[str, Claim] = {claim.claim_id: claim for claim in existing_claims}
    evidence: dict[str, EvidenceRef] = {row.evidence_id: row for row in existing_evidence}
    changes: list[dict[str, object]] = []

    episode_titles: dict[str, list[str]] = {ep.episode_id: [ep.title] for ep in episodes.values()}
    episode_claim_types: dict[str, set[str]] = {ep.episode_id: set() for ep in episodes.values()}
    for claim in claims.values():
        episode_claim_types.setdefault(claim.episode_id, set()).add(claim.claim_type)

    for event in sorted(event_rows, key=lambda row: (row.reference_at, row.event_id)):
        if any(event.event_id in ep.event_ids for ep in episodes.values()):
            continue
        context_only = is_context_only_event(event)
        event_entities = resolver.entities_in_event(event)
        candidate_id, score = _best_episode(event, event_entities, episodes.values(), episode_titles, episode_claim_types, now)
        effective_threshold = max(attach_threshold, 0.55) if context_only else attach_threshold
        if candidate_id is None or score < effective_threshold:
            if context_only:
                for entity in event_entities:
                    resolver.entities[entity.entity_id] = entity
                continue
            episode_id = _new_episode_id(event)
            actors, infrastructure, other = split_entities(event_entities)
            episode = ConflictEpisode(
                episode_id=episode_id,
                title=event.title,
                state="emerging",
                started_at=event.reference_at,
                last_updated_at=event.reference_at,
                countries=tuple(sorted({event.country} - {None})),  # type: ignore[arg-type]
                regions=tuple(sorted({event.region} - {None})),  # type: ignore[arg-type]
                event_ids=(event.event_id,),
                claim_ids=(),
                evidence_ids=(),
                actor_entity_ids=actors,
                infrastructure_entity_ids=infrastructure,
                other_entity_ids=other,
                change_flags=("episode_created",),
            )
            episodes[episode_id] = episode
            episode_titles[episode_id] = [event.title]
            episode_claim_types[episode_id] = set()
            changes.append({"episode_id": episode_id, "at": event.reference_at, "change_type": "episode_created", "event_id": event.event_id})
        else:
            episode_id = candidate_id
            episode = episodes[episode_id]
            actors, infrastructure, other = split_entities(event_entities)
            episode = replace(
                episode,
                last_updated_at=episode.last_updated_at if context_only else max(episode.last_updated_at, event.reference_at),
                countries=tuple(sorted(set(episode.countries) | ({event.country} if event.country else set()))),
                regions=tuple(sorted(set(episode.regions) | ({event.region} if event.region else set()))),
                event_ids=tuple(sorted(set(episode.event_ids) | {event.event_id})),
                actor_entity_ids=tuple(sorted(set(episode.actor_entity_ids) | set(actors))),
                infrastructure_entity_ids=tuple(sorted(set(episode.infrastructure_entity_ids) | set(infrastructure))),
                other_entity_ids=tuple(sorted(set(episode.other_entity_ids) | set(other))),
                change_flags=(),
                version=episode.version + 1,
            )
            episodes[episode_id] = episode
            if not context_only:
                episode_titles.setdefault(episode_id, []).append(event.title)

        for entity in event_entities:
            resolver.entities[entity.entity_id] = entity

        if context_only:
            # Context/sensor events may enrich the episode event trail after a strong
            # match, but they do not create claims/evidence, refresh conflict state,
            # or increase EvidenceStrength.
            continue

        claim, evd, claim_entities = extract_claim(event, episode_id, resolver)
        existing = claims.get(claim.claim_id)
        claims[claim.claim_id] = claim if existing is None else reconcile_claims([existing, claim])[0]
        evidence[evd.evidence_id] = evd
        episode_claim_types.setdefault(episode_id, set()).add(claim.claim_type)
        episode = episodes[episode_id]
        episodes[episode_id] = replace(
            episode,
            claim_ids=tuple(sorted(set(episode.claim_ids) | {claim.claim_id})),
            evidence_ids=tuple(sorted(set(episode.evidence_ids) | {evd.evidence_id})),
        )
        for entity in claim_entities:
            resolver.entities[entity.entity_id] = entity

    reconciled = reconcile_claims(claims.values())
    claims = {claim.claim_id: claim for claim in reconciled}

    final_episodes: list[ConflictEpisode] = []
    for episode in episodes.values():
        ep_claims = [claims[cid] for cid in episode.claim_ids if cid in claims]
        ep_events = [event for event in event_rows if event.event_id in episode.event_ids]
        previous_state = episode.state
        state = derive_episode_state(episode, ep_claims, ep_events, now=now)
        strength = calculate_evidence_strength(episode, ep_claims, ep_events, evidence.values(), resolver.entities.values(), now=now)
        flags = set(episode.change_flags)
        if state != previous_state:
            flags.add(f"state:{previous_state}->{state}")
            changes.append({"episode_id": episode.episode_id, "at": now.isoformat(), "change_type": "state_transition", "from": previous_state, "to": state})
        if any(claim.status == "disputed" for claim in ep_claims):
            flags.add("contradiction_present")
        if any(claim.status == "retracted" for claim in ep_claims):
            flags.add("retraction_present")
        final_episodes.append(replace(episode, state=state, evidence_strength=strength, change_flags=tuple(sorted(flags))))

    return (
        sorted(final_episodes, key=lambda ep: (ep.last_updated_at, ep.episode_id), reverse=True),
        sorted(claims.values(), key=lambda c: (c.last_seen_at, c.claim_id)),
        sorted(evidence.values(), key=lambda e: (e.observed_at, e.evidence_id)),
        sorted(resolver.entities.values(), key=lambda e: e.entity_id),
        changes,
    )


def is_context_only_event(event: Event) -> bool:
    return (
        event.verification_level == "sensor_signal"
        or event.source_kind == "sensor"
        or event.source_id in _CONTEXT_ONLY_SOURCE_IDS
        or event.event_type.startswith("gdacs_")
    )


def derive_episode_state(episode: ConflictEpisode, claims: Iterable[Claim], events: Iterable[Event], *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    claims = [claim for claim in claims if claim.status != "retracted"]
    event_rows = [event for event in events if not is_context_only_event(event)]
    last = parse_utc(episode.last_updated_at)
    stale_days = max(0.0, (now - last).total_seconds() / 86400)
    if stale_days >= 30:
        return "closed"

    latest_ceasefire = _latest_claim_time(claims, {"ceasefire"})
    latest_collapse = _latest_claim_time(claims, {"ceasefire_collapse"})
    if latest_ceasefire and (latest_collapse is None or latest_ceasefire >= latest_collapse):
        return "ceasefire"

    latest_escalation = _latest_claim_time(claims, _ESCALATION_CLAIMS)
    latest_deescalation = _latest_claim_time(claims, _DEESCALATION_CLAIMS)
    if latest_deescalation and (latest_escalation is None or latest_deescalation > latest_escalation):
        return "deescalating"
    if latest_escalation and (now - latest_escalation).total_seconds() <= 7 * 86400:
        recent_events = [event for event in event_rows if (now - parse_utc(event.reference_at)).total_seconds() <= 7 * 86400]
        if len(recent_events) >= 2 or any(claim.claim_type in {"ceasefire_collapse", "mobilization"} for claim in claims):
            return "escalating"
    if stale_days >= 7:
        return "stable"
    independent_sources = independent_event_source_count(event_rows)
    distinct_claim_count = len({claim.claim_id for claim in claims})
    if independent_sources >= 2 or distinct_claim_count >= 2:
        return "active"
    return "emerging"


def _latest_claim_time(claims: Iterable[Claim], claim_types: set[str]) -> datetime | None:
    values = [parse_utc(claim.last_seen_at) for claim in claims if claim.claim_type in claim_types]
    return max(values) if values else None


def calculate_evidence_strength(
    episode: ConflictEpisode,
    claims: Iterable[Claim],
    events: Iterable[Event],
    evidence: Iterable[EvidenceRef],
    entities: Iterable[Entity],
    *,
    now: datetime | None = None,
) -> EvidenceStrength:
    now = now or datetime.now(timezone.utc)
    events = [event for event in events if not is_context_only_event(event)]
    claims = list(claims)
    evidence = [row for row in evidence if row.evidence_id in episode.evidence_ids]
    entity_ids = set(episode.actor_entity_ids) | set(episode.infrastructure_entity_ids) | set(episode.other_entity_ids)
    entities = [entity for entity in entities if entity.entity_id in entity_ids]
    event_map = {event.event_id: event for event in events}
    independent_sources = independent_source_count(evidence, event_map)
    provider_independence = min(1.0, independent_sources / 4.0)
    research = 1.0 if any(row.verification_level == "research_coded" for row in evidence) else 0.0
    curated = 1.0 if any(row.verification_level == "curated_report" for row in evidence) else 0.0
    sensor = min(1.0, sum(1 for row in evidence if row.verification_level == "sensor_signal") / 2.0)
    geo = 1.0 if any(event.latitude is not None and event.longitude is not None for event in events) else (0.6 if episode.countries else 0.0)
    resolved_entities = len([entity for entity in entities if entity.canonical_name])
    entity_resolution = min(1.0, resolved_entities / 4.0)
    latest = max((parse_utc(event.reference_at) for event in events), default=parse_utc(episode.last_updated_at))
    age_hours = max(0.0, (now - latest).total_seconds() / 3600)
    recency = 1.0 if age_hours <= 12 else 0.8 if age_hours <= 24 else 0.6 if age_hours <= 72 else 0.3 if age_hours <= 168 else 0.1
    disputed = sum(1 for claim in claims if claim.status in {"disputed", "retracted"})
    contradiction_penalty = min(0.65, disputed / max(1, len(claims)) * 0.8)
    base = (
        provider_independence * 0.24 + research * 0.20 + curated * 0.14 + sensor * 0.07
        + geo * 0.12 + entity_resolution * 0.11 + recency * 0.12
    )
    overall = round(max(0.0, min(1.0, base * (1.0 - contradiction_penalty))) * 100)
    return EvidenceStrength(
        provider_independence=round(provider_independence, 3),
        research_coded=research,
        curated_institutional=curated,
        sensor_context=round(sensor, 3),
        geolocation=round(geo, 3),
        entity_resolution=round(entity_resolution, 3),
        recency=round(recency, 3),
        contradiction_penalty=round(contradiction_penalty, 3),
        overall_index=overall,
    )


def _best_episode(event: Event, entities: Iterable[Entity], episodes: Iterable[ConflictEpisode], episode_titles: dict[str, list[str]], episode_claim_types: dict[str, set[str]], now: datetime) -> tuple[str | None, float]:
    best_id = None
    best_score = 0.0
    actor_ids, infrastructure_ids, other_ids = split_entities(entities)
    event_infrastructure_ids = set(infrastructure_ids)
    event_country = event.country
    for episode in episodes:
        if event_country and episode.countries and event_country not in episode.countries:
            continue
        episode_infrastructure_ids = set(episode.infrastructure_entity_ids)
        # Resolved, mutually exclusive infrastructure identities are a hard
        # incompatibility. Regional proximity or a generic shared claim such as
        # "attack" must never collapse two different ports/bridges/pipelines into
        # one incident episode.
        if event_infrastructure_ids and episode_infrastructure_ids and event_infrastructure_ids.isdisjoint(episode_infrastructure_ids):
            continue
        delta_days = abs((parse_utc(event.reference_at) - parse_utc(episode.last_updated_at)).total_seconds()) / 86400
        if delta_days > 45:
            continue
        title_score = max((title_similarity(event.title, title) for title in episode_titles.get(episode.episode_id, [episode.title])), default=0.0)
        country_score = 1.0 if event_country and event_country in episode.countries else 0.4 if not event_country or not episode.countries else 0.0
        actor_overlap = _jaccard(set(actor_ids), set(episode.actor_entity_ids))
        infra_overlap = _jaccard(event_infrastructure_ids, episode_infrastructure_ids)
        other_overlap = _jaccard(set(other_ids), set(episode.other_entity_ids))
        event_claim_type = infer_claim_type(event.title, event.event_type)
        claim_overlap = 1.0 if event_claim_type in episode_claim_types.get(episode.episode_id, set()) else 0.0
        temporal = max(0.0, 1.0 - delta_days / 45.0)
        score = (
            country_score * 0.08 + actor_overlap * 0.25 + infra_overlap * 0.30
            + other_overlap * 0.22 + claim_overlap * 0.08 + title_score * 0.03 + temporal * 0.04
        )
        if score > best_score:
            best_id, best_score = episode.episode_id, score
    return best_id, best_score


def _new_episode_id(event: Event) -> str:
    return "ep_" + hashlib.sha256(f"{event.event_id}|{event.country or ''}".encode()).hexdigest()[:20]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)

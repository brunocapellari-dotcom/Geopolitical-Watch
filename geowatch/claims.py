from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Iterable

from .core import contains_phrase, normalize_text, publisher_from_url
from .entities import EntityResolver, split_entities, text_key
from .models import Claim, ConflictEpisode, Entity, Event, EvidenceRef

_CLAIM_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ceasefire_collapse", ("ceasefire collapse", "truce collapsed", "ceasefire ended")),
    ("ceasefire", ("ceasefire", "truce", "cessation of hostilities")),
    ("infrastructure_restoration", ("reopened", "reopens", "restored", "resumed operations", "operating normally", "back online")),
    ("infrastructure_disruption", ("closed", "closure", "disrupt", "halted", "suspended", "outage", "damaged")),
    ("attack", ("attack", "airstrike", "air strike", "missile strike", "drone strike", "shelling", "bombardment")),
    ("sanctions", ("sanction", "embargo", "asset freeze", "export ban", "import ban")),
    ("mobilization", ("mobilization", "mobilisation", "troop buildup", "troop build-up")),
    ("territorial_change", ("captured", "seized", "retook", "recaptured", "occupied")),
    ("humanitarian_displacement", ("displacement", "displaced", "refugee", "evacuation")),
    ("fatalities", ("killed", "dead", "fatalities", "deaths")),
)


_REFUTE_TERMS = (
    "denies", "denied", "not damaged", "no damage", "false report", "incorrect report",
    "remains open", "operating normally", "no disruption", "did not occur",
)
_RETRACTION_TERMS = ("retracted", "retraction", "correction", "corrected report")
_UPDATE_TERMS = ("reopened", "restored", "resumed operations", "back online", "revised", "updated")


def evidence_from_event(event: Event, *, relation: str = "reports") -> EvidenceRef:
    provider = event.publisher or publisher_from_url(event.source_url) or event.source_id
    evidence_id = "evd_" + hashlib.sha256(
        f"{event.event_id}|{relation}|{provider or ''}".encode()
    ).hexdigest()[:20]
    return EvidenceRef(
        evidence_id=evidence_id,
        event_id=event.event_id,
        source_id=event.source_id,
        verification_level=event.verification_level,
        evidence_class=event.evidence_class,
        relation=relation,  # type: ignore[arg-type]
        observed_at=event.published_at or event.reference_at,
        provider=provider,
        url=event.source_url,
        raw_ref=event.raw_ref,
    )


def extract_claim(event: Event, episode_id: str, resolver: EntityResolver) -> tuple[Claim, EvidenceRef, tuple[Entity, ...]]:
    entities = resolver.entities_in_event(event)
    actor_ids, infrastructure_ids, other_ids = split_entities(entities)
    claim_type = infer_claim_type(event.title, event.event_type)
    stance = infer_stance(event.title, claim_type)
    relation = "reports" if stance == "reports" else stance
    evidence = evidence_from_event(event, relation=relation)
    topic_key = build_topic_key(claim_type, event, entities)
    claim_id = "clm_" + hashlib.sha256(f"{episode_id}|{topic_key}".encode()).hexdigest()[:20]
    status = "unverified"
    if event.verification_level in {"research_coded", "curated_report"}:
        status = "supported"
    if stance == "refutes":
        status = "disputed"
    if any(contains_phrase(normalize_text(event.title), term) for term in _RETRACTION_TERMS):
        status = "retracted"
    return (
        Claim(
            claim_id=claim_id,
            episode_id=episode_id,
            claim_type=claim_type,
            topic_key=topic_key,
            statement=event.title,
            stance=stance,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            first_seen_at=event.reference_at,
            last_seen_at=event.reference_at,
            subject_entity_ids=actor_ids or other_ids[:1],
            object_entity_ids=infrastructure_ids,
            evidence_ids=(evidence.evidence_id,),
        ),
        evidence,
        entities,
    )


def merge_claim(existing: Claim, incoming: Claim) -> Claim:
    evidence_ids = tuple(sorted(set(existing.evidence_ids) | set(incoming.evidence_ids)))
    status = existing.status
    if incoming.status == "retracted":
        status = "retracted"
    elif incoming.stance == "refutes":
        status = "disputed"
    elif incoming.stance == "updates":
        status = "superseded" if existing.claim_type == "infrastructure_disruption" else "supported"
    elif incoming.status == "supported" or len(evidence_ids) >= 2:
        status = "supported"
    return replace(
        existing,
        last_seen_at=max(existing.last_seen_at, incoming.last_seen_at),
        evidence_ids=evidence_ids,
        status=status,
    )


def reconcile_claims(claims: Iterable[Claim]) -> list[Claim]:
    by_topic: dict[str, Claim] = {}
    ordered = sorted(claims, key=lambda claim: (claim.first_seen_at, claim.claim_id))
    for claim in ordered:
        previous = by_topic.get(claim.topic_key)
        by_topic[claim.topic_key] = claim if previous is None else merge_claim(previous, claim)

    # A restoration claim supersedes disruption claims for the same entity/topic root.
    restorations = [c for c in by_topic.values() if c.claim_type == "infrastructure_restoration"]
    for restoration in restorations:
        prefix = restoration.topic_key.replace("infrastructure_restoration", "")
        for key, claim in list(by_topic.items()):
            if claim.claim_type == "infrastructure_disruption" and claim.topic_key.replace("infrastructure_disruption", "") == prefix:
                by_topic[key] = replace(claim, status="superseded", last_seen_at=max(claim.last_seen_at, restoration.last_seen_at))
    return list(by_topic.values())


def infer_claim_type(title: str, event_type: str) -> str:
    normalized = normalize_text(title)
    for claim_type, patterns in _CLAIM_PATTERNS:
        if any(contains_phrase(normalized, pattern) for pattern in patterns):
            return claim_type
    if event_type and event_type not in {"media_report", "report", "sensor_detection"}:
        return event_type
    return "situation_report"


def infer_stance(title: str, claim_type: str) -> str:
    normalized = normalize_text(title)
    if any(contains_phrase(normalized, term) for term in _RETRACTION_TERMS):
        return "updates"
    if any(contains_phrase(normalized, term) for term in _REFUTE_TERMS):
        return "refutes"
    if claim_type == "infrastructure_restoration" or any(contains_phrase(normalized, term) for term in _UPDATE_TERMS):
        return "updates"
    return "supports"


def build_topic_key(claim_type: str, event: Event, entities: Iterable[Entity]) -> str:
    infra = sorted(text_key(e.canonical_name) for e in entities if e.entity_type in {"port", "airport", "pipeline", "refinery", "power", "canal", "strait", "waterway", "route", "infrastructure"})
    actors = sorted(text_key(e.canonical_name) for e in entities if e.entity_type in {"actor", "government", "armed_group", "organization"})
    anchor = "|".join(infra[:2] or actors[:2] or [text_key(event.country or event.region or "unknown")])
    # disruption/restoration intentionally share the same root so reconciliation can supersede.
    return f"{claim_type}|{anchor}"

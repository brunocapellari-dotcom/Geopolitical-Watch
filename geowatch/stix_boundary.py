from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable

from .models import Claim, Entity, Event, Relationship


def _stix_id(kind: str, stable_id: str) -> str:
    value = uuid.uuid5(uuid.NAMESPACE_URL, f"geowatch:{kind}:{stable_id}")
    return f"{kind}--{value}"


def _timestamp(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def export_bundle(
    *,
    entities: Iterable[Entity] = (),
    events: Iterable[Event] = (),
    relationships: Iterable[Relationship] = (),
    claims: Iterable[Claim] = (),
) -> dict[str, object]:
    objects: list[dict[str, object]] = []
    entity_refs: dict[str, str] = {}

    for entity in entities:
        stix_id = _stix_id("identity", entity.entity_id)
        entity_refs[entity.entity_id] = stix_id
        objects.append({
            "type": "identity",
            "spec_version": "2.1",
            "id": stix_id,
            "created": _timestamp(None),
            "modified": _timestamp(None),
            "name": entity.canonical_name,
            "identity_class": "organization" if entity.entity_type not in {"country", "region", "city"} else "system",
            "x_geowatch_entity_id": entity.entity_id,
            "x_geowatch_entity_type": entity.entity_type,
            "x_geowatch_aliases": list(entity.aliases),
        })

    for event in events:
        created = _timestamp(event.collected_at)
        objects.append({
            "type": "incident",
            "spec_version": "2.1",
            "id": _stix_id("incident", event.event_id),
            "created": created,
            "modified": created,
            "name": event.title,
            "description": event.title,
            "x_geowatch_event_id": event.event_id,
            "x_geowatch_event_type": event.event_type,
            "x_geowatch_source_id": event.source_id,
            "x_geowatch_reference_at": _timestamp(event.reference_at),
            "x_geowatch_verification_level": event.verification_level,
            "x_geowatch_evidence_class": event.evidence_class,
            "x_geowatch_raw_ref": event.raw_ref,
        })

    for relationship in relationships:
        source_ref = entity_refs.get(relationship.source_entity_id)
        target_ref = entity_refs.get(relationship.target_entity_id)
        if not source_ref or not target_ref:
            continue
        created = _timestamp(relationship.first_seen_at)
        row: dict[str, object] = {
            "type": "relationship",
            "spec_version": "2.1",
            "id": _stix_id("relationship", relationship.relationship_id),
            "created": created,
            "modified": _timestamp(relationship.last_seen_at),
            "relationship_type": "related-to",
            "source_ref": source_ref,
            "target_ref": target_ref,
            "x_geowatch_relationship_id": relationship.relationship_id,
            "x_geowatch_relationship_type": relationship.relationship_type,
            "x_geowatch_semantic_class": relationship.semantic_class,
            "x_geowatch_evidence_ids": list(relationship.evidence_ids),
        }
        if relationship.valid_from:
            row["start_time"] = _timestamp(relationship.valid_from)
        if relationship.valid_to:
            row["stop_time"] = _timestamp(relationship.valid_to)
        if relationship.confidence is not None:
            row["confidence"] = max(0, min(round(relationship.confidence * 100), 100))
            row["x_geowatch_confidence"] = relationship.confidence
        objects.append(row)

    for claim in claims:
        created = _timestamp(claim.first_seen_at)
        objects.append({
            "type": "x-geowatch-claim",
            "spec_version": "2.1",
            "id": _stix_id("x-geowatch-claim", claim.claim_id),
            "created": created,
            "modified": _timestamp(claim.last_seen_at),
            "statement": claim.statement,
            "x_geowatch_claim_id": claim.claim_id,
            "x_geowatch_episode_id": claim.episode_id,
            "x_geowatch_claim_type": claim.claim_type,
            "x_geowatch_topic_key": claim.topic_key,
            "x_geowatch_status": claim.status,
            "x_geowatch_evidence_ids": list(claim.evidence_ids),
        })

    return {"type": "bundle", "id": _stix_id("bundle", str(uuid.uuid4())), "objects": objects}


def validate_bundle_with_stix2(bundle: dict[str, object]) -> int:
    try:
        import stix2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("STIX validation requires the interoperability extra") from exc
    objects = bundle.get("objects") or []
    count = 0
    for row in objects:
        stix2.parse(row, allow_custom=True)
        count += 1
    return count


def import_boundary(bundle: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    """Read only Geowatch-tagged STIX objects; never promote them automatically."""
    output = {"entities": [], "events": [], "relationships": [], "claims": []}
    for raw in bundle.get("objects") or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("x_geowatch_entity_id"):
            output["entities"].append(dict(raw))
        elif raw.get("x_geowatch_event_id"):
            output["events"].append(dict(raw))
        elif raw.get("x_geowatch_relationship_id"):
            output["relationships"].append(dict(raw))
        elif raw.get("x_geowatch_claim_id"):
            output["claims"].append(dict(raw))
    return output

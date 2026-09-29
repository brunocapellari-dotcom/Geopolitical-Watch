from __future__ import annotations

from .models import Entity


def build_entity_dossier(store, entity_id: str, *, episode_limit: int = 5000) -> dict[str, object]:  # type: ignore[no-untyped-def]
    entities = {row.entity_id: row for row in store.load_entities()}
    entity: Entity | None = entities.get(entity_id)
    if entity is None:
        raise KeyError(entity_id)

    episodes = [
        row for row in store.load_episodes(limit=episode_limit)
        if entity_id in set(row.actor_entity_ids)
        or entity_id in set(row.infrastructure_entity_ids)
        or entity_id in set(row.other_entity_ids)
    ]
    event_ids = sorted({event_id for episode in episodes for event_id in episode.event_ids})
    events = store.load_events_by_ids(event_ids)
    episode_ids = {row.episode_id for row in episodes}
    claims = [row for row in store.load_claims() if row.episode_id in episode_ids]

    relationships = store.load_relationships(entity_id=entity_id)
    related_ids = {
        value
        for row in relationships
        for value in (row.source_entity_id, row.target_entity_id)
        if value != entity_id
    }
    related_entities = [entities[value] for value in sorted(related_ids) if value in entities]

    return {
        "schema_version": "geowatch-entity-dossier-v1",
        "entity": entity.to_dict(),
        "episodes": [row.to_dict() for row in episodes],
        "events": [row.to_dict() for row in events],
        "claims": [row.to_dict() for row in claims],
        "relationships": [row.to_dict() for row in relationships],
        "related_entities": [row.to_dict() for row in related_entities],
        "timeline": sorted(
            [
                {
                    "reference_at": row.reference_at,
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "title": row.title,
                    "source_id": row.source_id,
                }
                for row in events
            ],
            key=lambda row: (str(row["reference_at"]), str(row["event_id"])),
        ),
        "dossier_semantics": {
            "actor": "actor/organization/force dossier",
            "country": "country dossier",
            "infrastructure": "installation/chokepoint dossier",
            "all_content_requires_underlying_evidence": True,
        },
    }

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from .geo import normalize_country
from .models import Entity, Event

_WORD_RE = re.compile(r"[\w]+", re.UNICODE)

# Small, explicit multilingual alias seed. It is deliberately conservative: unknown
# names are not auto-translated or hallucinated. Operational deployments can extend
# config/entities.json without changing code.
MULTILINGUAL_ALIASES: dict[str, str] = {
    "kiev": "kyiv",
    "київ": "kyiv",
    "киев": "kyiv",
    "odessa": "odesa",
    "одеса": "odesa",
    "одесса": "odesa",
    "moskva": "moscow",
    "москва": "moscow",
    "россия": "russia",
    "украина": "ukraine",
    "україна": "ukraine",
    "غزة": "gaza",
    "قطاع غزة": "gaza strip",
    "إسرائيل": "israel",
    "اسرائيل": "israel",
    "البحر الأحمر": "red sea",
    "مضيق هرمز": "strait of hormuz",
    "باب المندب": "bab el mandeb",
    "قناة السويس": "suez canal",
    "mer rouge": "red sea",
    "mer noire": "black sea",
    "détroit d'ormuz": "strait of hormuz",
}

INFRASTRUCTURE_TYPES = {
    "port", "airport", "rail", "road", "pipeline", "refinery", "power",
    "canal", "strait", "waterway", "route", "infrastructure",
}


def text_key(value: str) -> str:
    text = " ".join(str(value).strip().split()).casefold()
    # Replace known multilingual phrases even when they are embedded in a longer
    # headline (e.g. Arabic/Cyrillic place name + English article text).
    for alias, canonical in sorted(MULTILINGUAL_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        alias_folded = alias.casefold()
        if alias_folded in text:
            text = text.replace(alias_folded, canonical)
    normalized = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    chars = [ch if ch.isalnum() else " " for ch in without_marks]
    return " ".join("".join(chars).split())


def token_key(value: str) -> tuple[str, ...]:
    return tuple(_WORD_RE.findall(text_key(value)))


class EntityResolver:
    def __init__(self, entities: Iterable[Entity] = ()) -> None:
        self.entities: dict[str, Entity] = {entity.entity_id: entity for entity in entities}
        self._alias_index: dict[str, str] = {}
        for entity in self.entities.values():
            for alias in (entity.canonical_name, *entity.aliases):
                key = text_key(alias)
                if key:
                    self._alias_index[key] = entity.entity_id

    @classmethod
    def from_json(cls, path: str | Path = "config/entities.json") -> "EntityResolver":
        p = Path(path)
        if not p.exists():
            return cls()
        body = json.loads(p.read_text(encoding="utf-8"))
        rows = body.get("entities", body if isinstance(body, list) else [])
        return cls(Entity.from_dict(row) for row in rows)

    def resolve_name(self, name: str, *, entity_type: str = "unknown", country: str | None = None) -> Entity:
        key = text_key(name)
        if key in self._alias_index:
            return self.entities[self._alias_index[key]]
        entity_id = "ent_" + hashlib.sha256(f"{entity_type}|{key}|{normalize_country(country) or ''}".encode()).hexdigest()[:20]
        entity = Entity(
            entity_id=entity_id,
            entity_type=entity_type,  # type: ignore[arg-type]
            canonical_name=" ".join(str(name).strip().split()),
            aliases=(),
            country=normalize_country(country),
        )
        self.entities[entity.entity_id] = entity
        self._alias_index[key] = entity.entity_id
        return entity

    def entities_in_event(self, event: Event) -> tuple[Entity, ...]:
        found: dict[str, Entity] = {}
        searchable = " ".join([event.title, event.region or "", *event.actors])
        searchable_key = f" {text_key(searchable)} "
        for alias, entity_id in self._alias_index.items():
            if not alias:
                continue
            if f" {alias} " in searchable_key:
                found[entity_id] = self.entities[entity_id]

        for actor in event.actors:
            if actor.strip():
                entity = self.resolve_name(actor, entity_type=_actor_type(actor), country=event.country)
                found[entity.entity_id] = entity
        if event.country:
            country = normalize_country(event.country) or event.country
            entity = self.resolve_name(country, entity_type="country", country=country)
            found[entity.entity_id] = entity
        if event.region:
            entity = self.resolve_name(event.region, entity_type="region", country=event.country)
            found[entity.entity_id] = entity
        return tuple(found.values())

    def upsert_location(self, entity: Entity, *, latitude: float | None, longitude: float | None) -> Entity:
        if latitude is None or longitude is None or (entity.latitude is not None and entity.longitude is not None):
            return entity
        updated = replace(entity, latitude=latitude, longitude=longitude)
        self.entities[entity.entity_id] = updated
        return updated


def split_entities(entities: Iterable[Entity]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    actors: list[str] = []
    infrastructure: list[str] = []
    other: list[str] = []
    for entity in entities:
        if entity.entity_type in {"actor", "government", "armed_group", "organization"}:
            actors.append(entity.entity_id)
        elif entity.entity_type in INFRASTRUCTURE_TYPES:
            infrastructure.append(entity.entity_id)
        elif entity.entity_type != "country":
            other.append(entity.entity_id)
    return tuple(sorted(set(actors))), tuple(sorted(set(infrastructure))), tuple(sorted(set(other)))


def _actor_type(name: str) -> str:
    key = text_key(name)
    if any(term in key for term in ("government", "ministry", "army", "navy", "air force", "forces")):
        return "government"
    if any(term in key for term in ("brigade", "militia", "front", "movement", "rebels", "group")):
        return "armed_group"
    if any(term in key for term in ("united nations", "nato", "organization", "organisation")):
        return "organization"
    return "actor"

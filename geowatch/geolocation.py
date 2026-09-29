from __future__ import annotations

from dataclasses import asdict, dataclass

from .entities import EntityResolver
from .models import Entity


@dataclass(frozen=True)
class GeolocationResult:
    entity_id: str
    canonical_name: str
    latitude: float | None
    longitude: float | None
    confidence: float
    method: str
    country: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def from_source_coordinates(
    *,
    name: str,
    latitude: float,
    longitude: float,
    entity_id: str = "source-coordinate",
    country: str | None = None,
) -> GeolocationResult:
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("invalid coordinates")
    return GeolocationResult(
        entity_id=entity_id,
        canonical_name=name.strip() or entity_id,
        latitude=latitude,
        longitude=longitude,
        confidence=1.0,
        method="source-provided",
        country=country,
    )


def resolve_known_location(
    name: str,
    *,
    resolver: EntityResolver,
    country: str | None = None,
    entity_type: str = "unknown",
) -> GeolocationResult:
    """Resolve only against governed entities; unknown places are never guessed."""
    entity: Entity = resolver.resolve_name(name, entity_type=entity_type, country=country)
    positioned = entity.latitude is not None and entity.longitude is not None
    return GeolocationResult(
        entity_id=entity.entity_id,
        canonical_name=entity.canonical_name,
        latitude=entity.latitude,
        longitude=entity.longitude,
        confidence=1.0 if positioned else 0.0,
        method="governed-entity-registry" if positioned else "unresolved",
        country=entity.country,
    )

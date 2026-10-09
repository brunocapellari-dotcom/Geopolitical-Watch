from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

VerificationLevel = Literal["research_coded", "curated_report", "osint_signal", "sensor_signal"]
EvidenceClass = Literal["observed", "inferred", "estimated"]
LocationSource = Literal["reported", "inferred", "unknown"]
ImpactArea = Literal[
    "energy", "fertilizers", "shipping", "trade", "fx", "agriculture",
    "logistics", "humanitarian", "infrastructure"
]
EntityType = Literal[
    "country", "region", "city", "actor", "government", "armed_group",
    "organization", "port", "airport", "rail", "road", "pipeline", "refinery",
    "power", "canal", "strait", "waterway", "route", "infrastructure", "unknown"
]
ClaimStatus = Literal["unverified", "supported", "disputed", "retracted", "superseded"]
EvidenceRelation = Literal["supports", "refutes", "updates", "reports"]
RelationshipSemanticClass = Literal["observed", "reported", "inferred", "estimated", "derived"]
EpisodeState = Literal["emerging", "active", "escalating", "stable", "deescalating", "ceasefire", "closed"]


@dataclass(frozen=True)
class Event:
    event_id: str
    source_id: str
    source_kind: str
    title: str
    event_type: str
    reference_at: str
    collected_at: str
    verification_level: VerificationLevel
    evidence_class: EvidenceClass = "observed"
    published_at: str | None = None
    source_event_id: str | None = None
    country: str | None = None
    region: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_source: LocationSource = "unknown"
    geolocation_method: str | None = None
    geolocation_confidence: float | None = None
    fatalities_best: int | None = None
    actors: tuple[str, ...] = ()
    source_url: str | None = None
    publisher: str | None = None
    impact_areas: tuple[ImpactArea, ...] = ()
    impact_evidence_class: EvidenceClass = "inferred"
    raw_ref: str | None = None

    def __post_init__(self) -> None:
        if self.geolocation_confidence is not None and not 0.0 <= self.geolocation_confidence <= 1.0:
            raise ValueError("geolocation_confidence must be between 0 and 1")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["actors"] = list(self.actors)
        row["impact_areas"] = list(self.impact_areas)
        return row

    @classmethod
    def from_dict(cls, row: dict[str, object]) -> "Event":
        data = dict(row)
        data["actors"] = tuple(data.get("actors") or ())
        data["impact_areas"] = tuple(data.get("impact_areas") or ())
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: EntityType
    canonical_name: str
    aliases: tuple[str, ...] = ()
    raw_names: tuple[str, ...] = ()
    normalized_name: str | None = None
    resolution_confidence: float | None = None
    country: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    external_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.resolution_confidence is not None and not 0.0 <= self.resolution_confidence <= 1.0:
            raise ValueError("resolution_confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["aliases"] = list(self.aliases)
        row["raw_names"] = list(self.raw_names)
        row["external_ids"] = list(self.external_ids)
        return row

    @classmethod
    def from_dict(cls, row: dict[str, object]) -> "Entity":
        data = dict(row)
        data["aliases"] = tuple(data.get("aliases") or ())
        data["raw_names"] = tuple(data.get("raw_names") or ())
        data["external_ids"] = tuple(data.get("external_ids") or ())
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    event_id: str
    source_id: str
    verification_level: VerificationLevel
    evidence_class: EvidenceClass
    relation: EvidenceRelation
    observed_at: str
    provider: str | None = None
    url: str | None = None
    raw_ref: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: dict[str, object]) -> "EvidenceRef":
        return cls(**row)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Claim:
    claim_id: str
    episode_id: str
    claim_type: str
    topic_key: str
    statement: str
    stance: EvidenceRelation
    status: ClaimStatus
    first_seen_at: str
    last_seen_at: str
    subject_entity_ids: tuple[str, ...] = ()
    object_entity_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["subject_entity_ids"] = list(self.subject_entity_ids)
        row["object_entity_ids"] = list(self.object_entity_ids)
        row["evidence_ids"] = list(self.evidence_ids)
        return row

    @classmethod
    def from_dict(cls, row: dict[str, object]) -> "Claim":
        data = dict(row)
        data["subject_entity_ids"] = tuple(data.get("subject_entity_ids") or ())
        data["object_entity_ids"] = tuple(data.get("object_entity_ids") or ())
        data["evidence_ids"] = tuple(data.get("evidence_ids") or ())
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Relationship:
    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    semantic_class: RelationshipSemanticClass
    first_seen_at: str
    last_seen_at: str
    valid_from: str | None = None
    valid_to: str | None = None
    confidence: float | None = None
    source_quality: float | None = None
    derivation_method: str | None = None
    derivation_version: str | None = None
    evidence_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    derived_from: tuple[str, ...] = ()
    provenance: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if _parse_relationship_time(self.last_seen_at) < _parse_relationship_time(self.first_seen_at):
            raise ValueError("last_seen_at must not precede first_seen_at")
        if self.valid_from and self.valid_to and _parse_relationship_time(self.valid_to) < _parse_relationship_time(self.valid_from):
            raise ValueError("valid_to must not precede valid_from")
        for name, value in (("confidence", self.confidence), ("source_quality", self.source_quality)):
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        for field in ("evidence_ids", "source_ids", "contradicts", "supersedes", "derived_from"):
            row[field] = list(getattr(self, field))
        return row

    @classmethod
    def from_dict(cls, row: dict[str, object]) -> "Relationship":
        data = dict(row)
        for field in ("evidence_ids", "source_ids", "contradicts", "supersedes", "derived_from"):
            data[field] = tuple(data.get(field) or ())
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True)
class EvidenceStrength:
    provider_independence: float
    research_coded: float
    curated_institutional: float
    sensor_context: float
    geolocation: float
    entity_resolution: float
    recency: float
    contradiction_penalty: float
    overall_index: int
    method_version: str = "geowatch-evidence-strength-v0.5"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: dict[str, object]) -> "EvidenceStrength":
        return cls(**row)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ConflictEpisode:
    episode_id: str
    title: str
    state: EpisodeState
    started_at: str
    last_updated_at: str
    countries: tuple[str, ...]
    regions: tuple[str, ...]
    event_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    actor_entity_ids: tuple[str, ...] = ()
    infrastructure_entity_ids: tuple[str, ...] = ()
    other_entity_ids: tuple[str, ...] = ()
    change_flags: tuple[str, ...] = ()
    evidence_strength: EvidenceStrength | None = None
    version: int = 1

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        for field in (
            "countries", "regions", "event_ids", "claim_ids", "evidence_ids",
            "actor_entity_ids", "infrastructure_entity_ids", "other_entity_ids", "change_flags",
        ):
            row[field] = list(getattr(self, field))
        if self.evidence_strength is not None:
            row["evidence_strength"] = self.evidence_strength.to_dict()
        return row

    @classmethod
    def from_dict(cls, row: dict[str, object]) -> "ConflictEpisode":
        data = dict(row)
        for field in (
            "countries", "regions", "event_ids", "claim_ids", "evidence_ids",
            "actor_entity_ids", "infrastructure_entity_ids", "other_entity_ids", "change_flags",
        ):
            data[field] = tuple(data.get(field) or ())
        strength = data.get("evidence_strength")
        if isinstance(strength, dict):
            data["evidence_strength"] = EvidenceStrength.from_dict(strength)
        return cls(**data)  # type: ignore[arg-type]


def _parse_relationship_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

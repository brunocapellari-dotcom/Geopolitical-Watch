from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


EpistemicClass = Literal["OBSERVADO", "RELATADO", "ESTIMADO", "INFERIDO", "NAO_CONFIRMADO"]
SourceState = Literal["HEALTHY", "DEGRADED", "BROKEN", "BLOCKED", "RETIRED"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceContract(ContractModel):
    source_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    authority: str | None = None
    country: str | None = None
    language: str | None = None
    url: HttpUrl | None = None
    state: SourceState = "DEGRADED"
    source_quality: float | None = Field(default=None, ge=0.0, le=1.0)


class ObservationContract(ContractModel):
    observation_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    collected_at: datetime
    reference_at: datetime | None = None
    publication_at: datetime | None = None
    raw_ref: str = Field(min_length=1)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_type: str | None = None
    language: str | None = None


class EvidenceContract(ContractModel):
    evidence_id: str = Field(min_length=1)
    observation_id: str | None = None
    source_id: str = Field(min_length=1)
    event_id: str | None = None
    claim_id: str | None = None
    relation: Literal["supports", "refutes", "updates", "reports"]
    epistemic_class: EpistemicClass
    observed_at: datetime
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    raw_ref: str | None = None


class ClaimContract(ContractModel):
    claim_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    topic_key: str = Field(min_length=1)
    status: Literal["unverified", "supported", "disputed", "retracted", "superseded"]
    epistemic_class: EpistemicClass
    first_seen_at: datetime
    last_seen_at: datetime
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_ids: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _time_order(self) -> "ClaimContract":
        if self.last_seen_at < self.first_seen_at:
            raise ValueError("last_seen_at must not precede first_seen_at")
        return self


class LocationContract(ContractModel):
    location_id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    country: str | None = None
    region: str | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    method: str | None = None


class ActorContract(ContractModel):
    actor_id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    actor_type: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    country: str | None = None


class EventContract(ContractModel):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    reference_at: datetime
    collected_at: datetime
    publication_at: datetime | None = None
    source_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    actor_ids: tuple[str, ...] = ()
    location_id: str | None = None
    epistemic_class: EpistemicClass
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ConflictContract(ContractModel):
    conflict_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    state: Literal["emerging", "active", "escalating", "stable", "deescalating", "ceasefire", "closed"]
    started_at: datetime
    last_updated_at: datetime
    event_ids: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    actor_ids: tuple[str, ...] = ()
    location_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _time_order(self) -> "ConflictContract":
        if self.last_updated_at < self.started_at:
            raise ValueError("last_updated_at must not precede started_at")
        return self


CONTRACT_MODELS = {
    "Source": SourceContract,
    "Observation": ObservationContract,
    "Evidence": EvidenceContract,
    "Claim": ClaimContract,
    "Location": LocationContract,
    "Actor": ActorContract,
    "Event": EventContract,
    "Conflict": ConflictContract,
}


def json_schema_bundle() -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Geopolitical Watch canonical contracts",
        "contracts": {name: model.model_json_schema(mode="validation") for name, model in CONTRACT_MODELS.items()},
    }

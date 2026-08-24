from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

VerificationLevel = Literal["research_coded", "curated_report", "osint_signal", "sensor_signal"]
EvidenceClass = Literal["observed", "inferred", "estimated"]
ImpactArea = Literal[
    "energy", "fertilizers", "shipping", "trade", "fx", "agriculture",
    "logistics", "humanitarian", "infrastructure"
]


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
    latitude: float | None = None
    longitude: float | None = None
    fatalities_best: int | None = None
    actors: tuple[str, ...] = ()
    source_url: str | None = None
    publisher: str | None = None
    impact_areas: tuple[ImpactArea, ...] = ()
    impact_evidence_class: EvidenceClass = "inferred"
    raw_ref: str | None = None

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

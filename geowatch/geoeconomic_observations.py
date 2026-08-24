from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class GeoeconomicObservation:
    observation_id: str
    source_id: str
    reference_period: str
    publication_date: str | None
    collected_at: str
    origin: str | None
    destination: str | None
    commodity: str
    value: float
    unit: str
    evidence_class: str = "observed"
    source_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def validate_observation(row: GeoeconomicObservation) -> list[str]:
    issues: list[str] = []
    if not row.source_id: issues.append("missing_source_id")
    if not row.reference_period: issues.append("missing_reference_period")
    if not row.collected_at: issues.append("missing_collected_at")
    if not row.commodity: issues.append("missing_commodity")
    if not row.unit: issues.append("missing_unit")
    if row.evidence_class not in {"observed", "estimated", "inferred", "projected"}: issues.append("invalid_evidence_class")
    return issues


def bilateral_concentration(rows: Iterable[GeoeconomicObservation], *, origin: str, commodity: str) -> dict:
    values = [row for row in rows if row.origin == origin and row.commodity == commodity and row.value >= 0]
    total = sum(row.value for row in values)
    shares = [(row.destination or "unknown", row.value / total) for row in values] if total > 0 else []
    hhi = sum(share * share for _, share in shares)
    return {
        "origin": origin,
        "commodity": commodity,
        "total": total,
        "counterparty_shares": sorted(({"counterparty": cp, "share": round(s, 6)} for cp, s in shares), key=lambda x: x["share"], reverse=True),
        "hhi": round(hhi, 6),
        "effective_counterparties": round(1 / hhi, 3) if hhi > 0 else None,
        "observation_count": len(values),
        "methodology_notes": ["Concentration is descriptive exposure, not a forecast of disruption or loss."],
    }

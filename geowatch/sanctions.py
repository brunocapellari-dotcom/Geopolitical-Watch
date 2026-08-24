from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class SanctionMeasure:
    sanction_id: str
    authority: str
    regime: str
    target_name: str
    target_type: str
    measures: tuple[str, ...]
    effective_at: str | None = None
    revoked_at: str | None = None
    source_url: str | None = None
    source_record_id: str | None = None
    country_tags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        row = asdict(self)
        row["measures"] = list(self.measures)
        row["country_tags"] = list(self.country_tags)
        return row


def normalize_sanction(*, authority: str, regime: str, target_name: str, target_type: str,
                      measures: Iterable[str], effective_at: str | None = None, revoked_at: str | None = None,
                      source_url: str | None = None, source_record_id: str | None = None,
                      country_tags: Iterable[str] = ()) -> SanctionMeasure:
    fingerprint = "|".join([authority, regime, source_record_id or "", target_name, effective_at or ""])
    sanction_id = "san_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
    return SanctionMeasure(
        sanction_id=sanction_id, authority=authority, regime=regime, target_name=target_name,
        target_type=target_type, measures=tuple(sorted(set(measures))), effective_at=effective_at,
        revoked_at=revoked_at, source_url=source_url, source_record_id=source_record_id,
        country_tags=tuple(sorted(set(country_tags))),
    )


def active_measures(rows: Iterable[SanctionMeasure], *, as_of: str | None = None) -> list[SanctionMeasure]:
    result = []
    for row in rows:
        if row.revoked_at and (as_of is None or row.revoked_at <= as_of):
            continue
        if as_of is not None and row.effective_at and row.effective_at > as_of:
            continue
        result.append(row)
    return result


def sanctions_context(rows: Iterable[SanctionMeasure], *, countries: Iterable[str] = ()) -> dict:
    countries = set(countries)
    matched = [row for row in rows if not countries or countries & set(row.country_tags)]
    regimes = sorted({row.regime for row in matched})
    authorities = sorted({row.authority for row in matched})
    measures = sorted({measure for row in matched for measure in row.measures})
    return {
        "schema_version": "geowatch-sanctions-context-v1",
        "context_not_evidence": True,
        "designation_count": len(matched),
        "authorities": authorities,
        "regimes": regimes,
        "measure_types": measures,
        "records": [row.to_dict() for row in matched],
        "methodology_notes": [
            "Sanctions designations are legal/administrative records from the issuing authority; they are not a generic geopolitical risk score.",
            "Revocations, amendments, effective dates and jurisdiction must be preserved.",
            "Compliance or legal applicability requires jurisdiction-specific specialist review.",
        ],
    }

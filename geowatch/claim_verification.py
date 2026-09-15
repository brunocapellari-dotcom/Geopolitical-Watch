from __future__ import annotations

from collections.abc import Iterable, Mapping

from .history import parse_utc
from .models import Claim, Event, EvidenceRef
from .quality import SourceProfile
from .verdict import VerdictInput, VerdictResult, assess_claim

_LEVEL_RELIABILITY = {
    "research_coded": 0.88,
    "curated_report": 0.78,
    "sensor_signal": 0.82,
    "osint_signal": 0.45,
}


def verify_claim(
    claim: Claim,
    *,
    evidence: Mapping[str, EvidenceRef],
    events: Mapping[str, Event],
    source_profiles: Mapping[str, SourceProfile] | None = None,
) -> VerdictResult:
    rows = [evidence[eid] for eid in claim.evidence_ids if eid in evidence]
    linked_events = [events[row.event_id] for row in rows if row.event_id in events]

    providers = {
        (row.provider or row.source_id).strip().casefold()
        for row in rows
        if (row.provider or row.source_id).strip()
    }
    source_ids = {row.source_id for row in rows}
    official_source_count = sum(
        1
        for source_id in source_ids
        if source_profiles and source_profiles.get(source_id) and source_profiles[source_id].official_or_primary
    )
    physical_rows = [row for row in rows if row.verification_level == "sensor_signal"]
    support_count = sum(1 for row in rows if row.relation in {"supports", "reports", "updates"})
    refute_count = sum(1 for row in rows if row.relation == "refutes")

    timestamp_quality = _timestamp_quality(rows, linked_events)
    geolocation_quality = _geolocation_quality(linked_events)
    reliability_values = []
    for row in rows:
        value = _LEVEL_RELIABILITY.get(row.verification_level, 0.45)
        profile = source_profiles.get(row.source_id) if source_profiles else None
        if profile and profile.official_or_primary:
            value = max(value, 0.94)
        reliability_values.append(value)
    source_reliability = sum(reliability_values) / len(reliability_values) if reliability_values else 0.0
    physical_quality = max((_physical_quality(row, events.get(row.event_id)) for row in physical_rows), default=0.0)

    return assess_claim(VerdictInput(
        claim_id=claim.claim_id,
        timestamp_quality=timestamp_quality,
        geolocation_quality=geolocation_quality,
        source_count=len(rows),
        independent_source_count=len(providers),
        physical_evidence_count=len(physical_rows),
        official_source_count=official_source_count,
        support_count=support_count,
        refute_count=refute_count,
        source_reliability=source_reliability,
        physical_evidence_quality=physical_quality,
        explicit_retraction=claim.status == "retracted",
    ))


def verify_claims(
    claims: Iterable[Claim],
    *,
    evidence: Iterable[EvidenceRef],
    events: Iterable[Event],
    source_profiles: Mapping[str, SourceProfile] | None = None,
) -> dict[str, VerdictResult]:
    evidence_map = {row.evidence_id: row for row in evidence}
    event_map = {row.event_id: row for row in events}
    return {
        claim.claim_id: verify_claim(
            claim,
            evidence=evidence_map,
            events=event_map,
            source_profiles=source_profiles,
        )
        for claim in claims
    }


def _timestamp_quality(evidence: list[EvidenceRef], events: list[Event]) -> float:
    values = []
    for row in evidence:
        try:
            parse_utc(row.observed_at)
            values.append(1.0)
        except (TypeError, ValueError):
            values.append(0.0)
    for event in events:
        try:
            reference = parse_utc(event.reference_at)
            if event.published_at:
                published = parse_utc(event.published_at)
                lag_hours = abs((published - reference).total_seconds()) / 3600
                values.append(1.0 if lag_hours <= 12 else 0.8 if lag_hours <= 48 else 0.6)
            else:
                values.append(0.75)
        except (TypeError, ValueError):
            values.append(0.0)
    return round(sum(values) / len(values), 3) if values else 0.0


def _geolocation_quality(events: list[Event]) -> float:
    if not events:
        return 0.0
    best = 0.0
    for event in events:
        if event.latitude is not None and event.longitude is not None:
            best = max(best, 0.95)
        elif event.region:
            best = max(best, 0.65)
        elif event.country:
            best = max(best, 0.45)
    return best


def _physical_quality(evidence: EvidenceRef, event: Event | None) -> float:
    if evidence.verification_level != "sensor_signal":
        return 0.0
    if event and event.latitude is not None and event.longitude is not None:
        return 0.85
    return 0.65

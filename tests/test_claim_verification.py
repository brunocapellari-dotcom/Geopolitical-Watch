from __future__ import annotations

import unittest

from geowatch.claim_verification import verify_claim
from geowatch.models import Claim, Event, EvidenceRef


def _event(event_id: str, source_id: str, *, lat: float = 10.0, lon: float = 20.0) -> Event:
    return Event(
        event_id=event_id,
        source_id=source_id,
        source_kind="test",
        title="reported event",
        event_type="attack",
        reference_at="2026-09-15T00:00:00+00:00",
        collected_at="2026-09-15T00:05:00+00:00",
        verification_level="research_coded" if source_id == "ucdp_ged_26_1" else "sensor_signal",
        latitude=lat,
        longitude=lon,
    )


class ClaimVerificationTests(unittest.TestCase):
    def test_independent_research_and_sensor_evidence_can_confirm(self) -> None:
        claim = Claim(
            claim_id="claim-1",
            episode_id="episode-1",
            claim_type="attack",
            topic_key="attack|example",
            statement="reported event",
            stance="supports",
            status="supported",
            first_seen_at="2026-09-15T00:00:00+00:00",
            last_seen_at="2026-09-15T00:05:00+00:00",
            evidence_ids=("e1", "e2"),
        )
        evidence = {
            "e1": EvidenceRef(
                evidence_id="e1", event_id="event-1", source_id="ucdp_ged_26_1",
                verification_level="research_coded", evidence_class="observed", relation="supports",
                observed_at="2026-09-15T00:00:00+00:00", provider="UCDP",
            ),
            "e2": EvidenceRef(
                evidence_id="e2", event_id="event-2", source_id="nasa_firms_context",
                verification_level="sensor_signal", evidence_class="observed", relation="supports",
                observed_at="2026-09-15T00:04:00+00:00", provider="NASA FIRMS",
            ),
        }
        events = {
            "event-1": _event("event-1", "ucdp_ged_26_1"),
            "event-2": _event("event-2", "nasa_firms_context"),
        }
        result = verify_claim(claim, evidence=evidence, events=events)
        self.assertEqual(result.verdict, "CONFIRMADO")
        self.assertGreaterEqual(result.confidence, 78)
        self.assertEqual(result.factors["independent_source_count"], 2)

    def test_duplicate_provider_does_not_count_as_independent_corroboration(self) -> None:
        claim = Claim(
            claim_id="claim-2",
            episode_id="episode-1",
            claim_type="attack",
            topic_key="attack|example",
            statement="reported event",
            stance="supports",
            status="unverified",
            first_seen_at="2026-09-15T00:00:00+00:00",
            last_seen_at="2026-09-15T00:02:00+00:00",
            evidence_ids=("e1", "e2"),
        )
        evidence = {
            "e1": EvidenceRef(
                evidence_id="e1", event_id="event-1", source_id="gdelt_conflict_news",
                verification_level="osint_signal", evidence_class="observed", relation="supports",
                observed_at="2026-09-15T00:00:00+00:00", provider="Same Publisher",
            ),
            "e2": EvidenceRef(
                evidence_id="e2", event_id="event-2", source_id="gdelt_conflict_news",
                verification_level="osint_signal", evidence_class="observed", relation="supports",
                observed_at="2026-09-15T00:02:00+00:00", provider="Same Publisher",
            ),
        }
        events = {
            "event-1": _event("event-1", "gdelt_conflict_news"),
            "event-2": _event("event-2", "gdelt_conflict_news"),
        }
        result = verify_claim(claim, evidence=evidence, events=events)
        self.assertEqual(result.factors["independent_source_count"], 1)
        self.assertNotEqual(result.verdict, "CONFIRMADO")


if __name__ == "__main__":
    unittest.main()

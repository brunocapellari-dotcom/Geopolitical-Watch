from __future__ import annotations

import json
import unittest

from geowatch.claim_verification import verify_claim
from geowatch.models import Claim, Event, EvidenceRef
from geowatch.reconciliation import match_score
from geowatch.research_gateway import ResearchRequest, plan_research
from geowatch.sources import gdelt


def event(
    event_id: str,
    *,
    title: str = "Reported incident",
    country: str = "Example",
    reference_at: str = "2026-10-08T10:00:00+00:00",
    published_at: str | None = "2026-10-08T10:00:00+00:00",
    provider: str = "Outlet A",
) -> Event:
    return Event(
        event_id=event_id,
        source_id="gdelt_conflict_news",
        source_kind="news",
        title=title,
        event_type="media_report",
        reference_at=reference_at,
        published_at=published_at,
        collected_at="2026-10-08T12:00:00+00:00",
        verification_level="osint_signal",
        country=country,
        publisher=provider,
        source_url=f"https://{provider.casefold().replace(' ', '-')}.example/{event_id}",
    )


def evidence(event_id: str, evidence_id: str, provider: str, relation: str = "supports") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        event_id=event_id,
        source_id="gdelt_conflict_news",
        verification_level="osint_signal",
        evidence_class="observed",
        relation=relation,  # type: ignore[arg-type]
        observed_at="2026-10-08T12:00:00+00:00",
        provider=provider,
        url=f"https://{provider.casefold().replace(' ', '-')}.example/{event_id}",
    )


def claim(*evidence_ids: str) -> Claim:
    return Claim(
        claim_id="claim-adversarial",
        episode_id="ep-adversarial",
        claim_type="situation_report",
        topic_key="situation_report|example",
        statement="Reported incident",
        stance="supports",
        status="unverified",
        first_seen_at="2026-10-08T10:00:00+00:00",
        last_seen_at="2026-10-08T12:00:00+00:00",
        evidence_ids=tuple(evidence_ids),
    )


class AdversarialGateTests(unittest.TestCase):
    def test_single_fake_report_cannot_become_confirmed(self) -> None:
        ev = event("fake-1", provider="Unknown Outlet")
        evd = evidence("fake-1", "e1", "Unknown Outlet")
        result = verify_claim(claim("e1"), evidence={"e1": evd}, events={ev.event_id: ev})
        self.assertNotEqual("CONFIRMADO", result.verdict)
        self.assertLess(result.factors["independent_source_count"], 2)

    def test_conflicting_sources_remain_conflicting(self) -> None:
        a = event("support", provider="Outlet A")
        b = event("refute", provider="Outlet B")
        evidence_map = {
            "e1": evidence("support", "e1", "Outlet A", "supports"),
            "e2": evidence("refute", "e2", "Outlet B", "refutes"),
        }
        result = verify_claim(
            claim("e1", "e2"),
            evidence=evidence_map,
            events={a.event_id: a, b.event_id: b},
        )
        self.assertEqual("CONFLITANTE", result.verdict)

    def test_wrong_country_cannot_reconcile_as_same_event(self) -> None:
        a = event("loc-a", country="Country A")
        b = event("loc-b", country="Country B")
        result = match_score(a, b)
        self.assertEqual(0.0, result["score"])
        self.assertFalse(result["country_match"])

    def test_old_media_repost_cannot_pass_confirmation_timestamp_gate(self) -> None:
        old = event(
            "old-repost",
            title="Video reposted today about an old incident",
            reference_at="2026-01-01T10:00:00+00:00",
            published_at="2026-10-08T10:00:00+00:00",
            provider="Outlet A",
        )
        fresh = event(
            "fresh-mention",
            title="Video reposted today about an old incident",
            reference_at="2026-01-01T10:00:00+00:00",
            published_at="2026-10-08T11:00:00+00:00",
            provider="Outlet B",
        )
        evidence_map = {
            "e1": evidence("old-repost", "e1", "Outlet A"),
            "e2": evidence("fresh-mention", "e2", "Outlet B"),
        }
        result = verify_claim(
            claim("e1", "e2"),
            evidence=evidence_map,
            events={old.event_id: old, fresh.event_id: fresh},
        )
        self.assertNotEqual("CONFIRMADO", result.verdict)
        self.assertLess(result.factors["timestamp_quality"], 0.7)

    def test_prompt_injection_like_hostile_content_requires_isolated_browser(self) -> None:
        request = ResearchRequest(
            source_id="hostile-osint",
            url="https://example.org/post",
            kind="article",
            terms_approved=True,
            requires_js=True,
            hostile_content=True,
            browser_isolated=False,
        )
        with self.assertRaises(ValueError):
            plan_research(request)

    def test_malformed_source_payload_fails_closed(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            gdelt.parse(b"{malformed")
        with self.assertRaises(ValueError):
            gdelt.parse(b'{"articles":"not-a-list"}')


if __name__ == "__main__":
    unittest.main()

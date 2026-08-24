from __future__ import annotations

import unittest

from geowatch.core import cluster_events, corroboration_status, infer_impact_areas, score_cluster
from geowatch.models import Event


class CoreTests(unittest.TestCase):
    def event(self, event_id: str, publisher: str, verification: str = "osint_signal") -> Event:
        return Event(
            event_id=event_id,
            source_id="fixture",
            source_kind="news" if verification == "osint_signal" else "research",
            title="Missile attack disrupts major port operations",
            event_type="media_report",
            reference_at="2026-08-24T10:00:00+00:00",
            published_at="2026-08-24T10:00:00+00:00",
            collected_at="2026-08-24T10:05:00+00:00",
            verification_level=verification,
            source_url=f"https://{publisher}/{event_id}",
            publisher=publisher,
            impact_areas=("shipping", "logistics"),
        )

    def test_phrase_matching_does_not_match_report_as_port(self) -> None:
        self.assertEqual(infer_impact_areas("A new report was published"), ())
        impacts = infer_impact_areas("Port blockade affects crude tanker traffic")
        self.assertIn("shipping", impacts)
        self.assertIn("trade", impacts)
        self.assertIn("energy", impacts)

    def test_multi_publisher_news_is_corroborated(self) -> None:
        cluster = cluster_events([self.event("a", "reuters.com"), self.event("b", "bbc.com")])[0]
        self.assertEqual(cluster.provider_count, 2)
        self.assertEqual(corroboration_status(cluster), "multi_provider_osint")

    def test_same_publisher_does_not_fake_corroboration(self) -> None:
        cluster = cluster_events([self.event("a", "example.com"), self.event("b", "example.com")])[0]
        self.assertEqual(cluster.provider_count, 1)
        self.assertEqual(corroboration_status(cluster), "single_provider_signal")

    def test_research_coded_ranks_above_single_news(self) -> None:
        news_score = score_cluster(cluster_events([self.event("a", "example.com")])[0])
        coded = self.event("b", "ucdp", "research_coded")
        coded_score = score_cluster(cluster_events([coded])[0])
        self.assertGreater(coded_score, news_score)


if __name__ == "__main__":
    unittest.main()

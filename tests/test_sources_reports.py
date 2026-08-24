from __future__ import annotations

import json
import unittest

from geowatch.core import cluster_events
from geowatch.reports import build_feed, build_report, render_markdown
from geowatch.sources import gdelt, reliefweb, ucdp


class SourceReportTests(unittest.TestCase):
    def test_gdelt_news_keeps_publisher_and_link(self) -> None:
        payload = json.dumps({"articles": [
            {"title": "Missile attack disrupts major port operations", "url": "https://reuters.com/a", "seendate": "20260824T101500Z"},
            {"title": "Missile attack disrupts major port operations", "url": "https://bbc.com/b", "seendate": "20260824T101600Z"}
        ]}).encode()
        events = gdelt.parse(payload, collected_at="2026-08-24T10:20:00+00:00")
        self.assertEqual({e.publisher for e in events}, {"reuters.com", "bbc.com"})
        report = build_report(cluster_events(events), generated_at="2026-08-24T11:00:00+00:00")
        self.assertEqual(report["news_count"], 2)
        markdown = render_markdown(report)
        self.assertIn("https://reuters.com/a", markdown)
        self.assertIn("https://bbc.com/b", markdown)
        feed = build_feed(report)
        self.assertEqual(feed["schema_version"], "geowatch-feed-v1")

    def test_ucdp_is_research_coded(self) -> None:
        payload = json.dumps({"Result": [{
            "id": 1, "type_of_violence": 1, "dyad_name": "Government - Group", "side_a": "Government",
            "side_b": "Group", "country": "Testland", "region": "Region", "latitude": 1.0, "longitude": 2.0,
            "date_start": "2026-08-23", "best": 12
        }]}).encode()
        event = ucdp.parse(payload, collected_at="2026-08-24T12:00:00+00:00")[0]
        self.assertEqual(event.verification_level, "research_coded")
        self.assertEqual(event.fatalities_best, 12)
        self.assertEqual(event.actors, ("Government", "Group"))

    def test_reliefweb_does_not_make_publisher_an_actor(self) -> None:
        payload = json.dumps({"data": [{"id": "r1", "fields": {
            "title": "Conflict situation report: port and oil disruption",
            "origin": "https://ocha.example/r1.pdf",
            "date": {"created": "2026-08-24T09:00:00+00:00"},
            "primary_country": {"name": "Testland"},
            "source": [{"shortname": "OCHA"}]
        }}]}).encode()
        event = reliefweb.parse(payload, collected_at="2026-08-24T09:05:00+00:00")[0]
        self.assertEqual(event.verification_level, "curated_report")
        self.assertEqual(event.publisher, "OCHA")
        self.assertEqual(event.actors, ())
        self.assertIn("shipping", event.impact_areas)
        self.assertIn("energy", event.impact_areas)


if __name__ == "__main__":
    unittest.main()

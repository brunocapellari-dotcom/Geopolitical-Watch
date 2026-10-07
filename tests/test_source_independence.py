from __future__ import annotations

import unittest

from geowatch.models import Event, EvidenceRef
from geowatch.source_independence import independent_source_count, source_dependency_groups


def event(event_id: str, title: str, publisher: str, url: str) -> Event:
    return Event(
        event_id=event_id,
        source_id="gdelt_conflict_news",
        source_kind="news",
        title=title,
        event_type="media_report",
        reference_at="2026-10-07T10:00:00+00:00",
        collected_at="2026-10-07T10:01:00+00:00",
        verification_level="osint_signal",
        source_url=url,
        publisher=publisher,
    )


def evidence(event_id: str, provider: str, url: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=f"ev_{event_id}",
        event_id=event_id,
        source_id="gdelt_conflict_news",
        verification_level="osint_signal",
        evidence_class="observed",
        relation="reports",
        observed_at="2026-10-07T10:01:00+00:00",
        provider=provider,
        url=url,
    )


class SourceIndependenceTests(unittest.TestCase):
    def test_same_provider_counts_once(self) -> None:
        events = {
            "a": event("a", "Port closure reported after overnight incident", "Example News", "https://example.com/a"),
            "b": event("b", "Authorities report port closure after incident", "Example News", "https://example.com/b"),
        }
        rows = [
            evidence("a", "Example News", "https://example.com/a"),
            evidence("b", "Example News", "https://example.com/b"),
        ]
        self.assertEqual(1, independent_source_count(rows, events))

    def test_near_identical_cross_publisher_headlines_are_dependency_grouped(self) -> None:
        title = "Government confirms border crossing closed after overnight clashes"
        events = {
            "a": event("a", title, "Outlet A", "https://a.example/story"),
            "b": event("b", title + " today", "Outlet B", "https://b.example/story"),
        }
        rows = [
            evidence("a", "Outlet A", "https://a.example/story"),
            evidence("b", "Outlet B", "https://b.example/story"),
        ]
        self.assertEqual(1, independent_source_count(rows, events))

    def test_explicit_shared_wire_origin_counts_once(self) -> None:
        events = {
            "a": event("a", "Reuters: Border crossing closed after clashes", "Outlet A", "https://a.example/story"),
            "b": event("b", "Officials close border crossing after clashes - Reuters", "Outlet B", "https://b.example/story"),
        }
        rows = [
            evidence("a", "Outlet A", "https://a.example/story"),
            evidence("b", "Outlet B", "https://b.example/story"),
        ]
        self.assertEqual(1, independent_source_count(rows, events))

    def test_distinct_reporting_remains_independent(self) -> None:
        events = {
            "a": event("a", "Local authorities announce border closure", "Outlet A", "https://a.example/story"),
            "b": event("b", "Aid agency reports queues forming at nearby crossings", "Outlet B", "https://b.example/story"),
        }
        rows = [
            evidence("a", "Outlet A", "https://a.example/story"),
            evidence("b", "Outlet B", "https://b.example/story"),
        ]
        groups = source_dependency_groups(rows, events)
        self.assertEqual(2, len(groups))


if __name__ == "__main__":
    unittest.main()

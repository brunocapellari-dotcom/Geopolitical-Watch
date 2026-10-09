from __future__ import annotations

import unittest

from geowatch.event_graph import build_event_graph, related_event_ids
from geowatch.models import ConflictEpisode, Event


def event(event_id: str, when: str) -> Event:
    return Event(
        event_id=event_id,
        source_id="test",
        source_kind="news",
        title=f"Event {event_id}",
        event_type="media_report",
        reference_at=when,
        collected_at=when,
        verification_level="osint_signal",
        country="Example",
    )


class EventGraphTests(unittest.TestCase):
    def test_timeline_relationships_are_ordered_and_non_causal(self) -> None:
        events = [
            event("e2", "2026-10-07T11:00:00+00:00"),
            event("e1", "2026-10-07T10:00:00+00:00"),
            event("e3", "2026-10-07T12:00:00+00:00"),
        ]
        episode = ConflictEpisode(
            episode_id="ep-1",
            title="Example episode",
            state="active",
            started_at="2026-10-07T10:00:00+00:00",
            last_updated_at="2026-10-07T12:00:00+00:00",
            countries=("Example",),
            regions=(),
            event_ids=("e1", "e2", "e3"),
            claim_ids=(),
            evidence_ids=(),
        )
        graph = build_event_graph([episode], events)
        relationships = {
            (row["source_event_id"], row["target_event_id"], row["relationship_type"])
            for row in graph["links"]
        }
        self.assertIn(("e1", "e2", "PRECEDES"), relationships)
        self.assertIn(("e2", "e1", "FOLLOWS"), relationships)
        self.assertIn(("e2", "e3", "PRECEDES"), relationships)
        self.assertIn(("e1", "e2", "RELATED_TO"), relationships)
        self.assertFalse(graph["automatic_causality"])
        self.assertNotIn("RESPONSE_TO", {row["relationship_type"] for row in graph["links"]})
        self.assertNotIn("ESCALATION_OF", {row["relationship_type"] for row in graph["links"]})

    def test_related_event_lookup_is_bidirectional_for_navigation(self) -> None:
        events = [
            event("a", "2026-10-07T10:00:00+00:00"),
            event("b", "2026-10-07T11:00:00+00:00"),
        ]
        episode = ConflictEpisode(
            episode_id="ep-2",
            title="Example",
            state="active",
            started_at=events[0].reference_at,
            last_updated_at=events[1].reference_at,
            countries=("Example",),
            regions=(),
            event_ids=("a", "b"),
            claim_ids=(),
            evidence_ids=(),
        )
        graph = build_event_graph([episode], events)
        self.assertEqual(["b"], related_event_ids(graph, "a"))
        self.assertEqual(["a"], related_event_ids(graph, "b"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from geowatch.convergence import converge_events
from geowatch.entities import EntityResolver
from geowatch.models import Event


def _event(event_id: str, title: str, hour: int, latitude: float, longitude: float) -> Event:
    return Event(
        event_id=event_id,
        source_id="gdelt_conflict_news",
        source_kind="news",
        title=title,
        event_type="media_report",
        reference_at=f"2026-09-15T{hour:02d}:00:00+00:00",
        collected_at=f"2026-09-15T{hour:02d}:05:00+00:00",
        published_at=f"2026-09-15T{hour:02d}:00:00+00:00",
        verification_level="osint_signal",
        country="Ukraine",
        region="Odesa",
        latitude=latitude,
        longitude=longitude,
        publisher=f"{event_id}.example",
        source_url=f"https://{event_id}.example/report",
        impact_areas=("shipping", "infrastructure"),
    )


class ConvergenceIdentityGuardTests(unittest.TestCase):
    def test_nearby_ports_in_same_region_and_same_claim_stay_separate(self) -> None:
        resolver = EntityResolver.from_json("config/entities.json")
        episodes, claims, evidence, _, _ = converge_events(
            [
                _event("odesa", "Port of Odesa attacked", 8, 46.49, 30.74),
                _event("chornomorsk", "Port of Chornomorsk attacked", 9, 46.30, 30.66),
            ],
            resolver=resolver,
            now=datetime(2026, 9, 15, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(2, len(episodes))
        self.assertEqual({("odesa",), ("chornomorsk",)}, {tuple(sorted(ep.event_ids)) for ep in episodes})
        self.assertEqual(2, len(claims))
        self.assertEqual(2, len(evidence))

    def test_same_port_paraphrases_still_converge(self) -> None:
        resolver = EntityResolver.from_json("config/entities.json")
        episodes, _, _, _, _ = converge_events(
            [
                _event("o1", "Port of Odesa damaged after missile strike", 8, 46.49, 30.74),
                _event("o2", "Odessa Port halted operations following attack", 9, 46.49, 30.74),
            ],
            resolver=resolver,
            now=datetime(2026, 9, 15, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(1, len(episodes))
        self.assertEqual(("o1", "o2"), tuple(sorted(episodes[0].event_ids)))


if __name__ == "__main__":
    unittest.main()

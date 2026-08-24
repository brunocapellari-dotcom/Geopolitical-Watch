from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from geowatch.convergence import converge_events, derive_episode_state
from geowatch.entities import EntityResolver
from geowatch.models import Event
from geowatch.storage import SQLiteStore


def ev(event_id: str, title: str, when: str, *, country: str = "Ukraine", publisher: str = "example.com", verification: str = "osint_signal") -> Event:
    return Event(
        event_id=event_id,
        source_id="test_source",
        source_kind="news",
        title=title,
        event_type="media_report",
        reference_at=when,
        collected_at=when,
        published_at=when,
        verification_level=verification,  # type: ignore[arg-type]
        country=country,
        publisher=publisher,
        source_url=f"https://{publisher}/{event_id}",
    )


class V05ConvergenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = EntityResolver.from_json("config/entities.json")
        self.now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)

    def test_multilingual_route_alias_resolves(self) -> None:
        event = ev("a1", "Shipping disruption reported in Mar Vermelho", "2026-08-24T10:00:00+00:00", country="Yemen")
        ids = {entity.entity_id for entity in self.resolver.entities_in_event(event)}
        self.assertIn("route_red_sea", ids)

    def test_same_infrastructure_paraphrases_converge(self) -> None:
        events = [
            ev("o1", "Port of Odesa damaged after missile strike", "2026-08-24T08:00:00+00:00"),
            ev("o2", "Odessa Port halted operations following attack", "2026-08-24T11:00:00+00:00", publisher="other.example"),
        ]
        episodes, *_ = converge_events(events, resolver=self.resolver, now=self.now)
        self.assertEqual(1, len(episodes))
        self.assertEqual({"o1", "o2"}, set(episodes[0].event_ids))

    def test_different_infrastructure_does_not_converge(self) -> None:
        events = [
            ev("p1", "Port of Odesa attacked", "2026-08-24T08:00:00+00:00"),
            ev("p2", "Port of Chornomorsk attacked", "2026-08-24T09:00:00+00:00", publisher="other.example"),
        ]
        episodes, *_ = converge_events(events, resolver=self.resolver, now=self.now)
        self.assertEqual(2, len(episodes))

    def test_refuting_evidence_marks_claim_disputed(self) -> None:
        events = [
            ev("c1", "Odesa Port closed after attack", "2026-08-24T08:00:00+00:00"),
            ev("c2", "Authority denies Odesa Port closed after attack", "2026-08-24T09:00:00+00:00", publisher="authority.example"),
        ]
        _, claims, *_ = converge_events(events, resolver=self.resolver, now=self.now)
        self.assertTrue(any(claim.status == "disputed" for claim in claims))

    def test_restoration_supersedes_disruption(self) -> None:
        events = [
            ev("r1", "Odesa Port closed after damage", "2026-08-24T07:00:00+00:00"),
            ev("r2", "Odesa Port reopened and resumed operations", "2026-08-24T10:00:00+00:00", publisher="port.example"),
        ]
        _, claims, *_ = converge_events(events, resolver=self.resolver, now=self.now)
        disruption = [claim for claim in claims if claim.claim_type == "infrastructure_disruption"]
        restoration = [claim for claim in claims if claim.claim_type == "infrastructure_restoration"]
        self.assertTrue(disruption and restoration)
        self.assertEqual("superseded", disruption[0].status)

    def test_ceasefire_sets_episode_state(self) -> None:
        event = ev("z1", "Ceasefire announced in Gaza", "2026-08-24T10:00:00+00:00", country="Palestine")
        episodes, *_ = converge_events([event], resolver=self.resolver, now=self.now)
        self.assertEqual("ceasefire", episodes[0].state)

    def test_stale_episode_closes(self) -> None:
        event = ev("s1", "Port of Odesa attacked", "2026-07-01T10:00:00+00:00")
        episodes, claims, *_ = converge_events([event], resolver=self.resolver, now=datetime(2026, 7, 1, 12, tzinfo=timezone.utc))
        state = derive_episode_state(episodes[0], claims, [event], now=datetime(2026, 8, 5, 12, tzinfo=timezone.utc))
        self.assertEqual("closed", state)

    def test_evidence_strength_is_bounded_triage_index(self) -> None:
        events = [
            ev("e1", "Odesa Port attacked", "2026-08-24T08:00:00+00:00", publisher="one.example"),
            ev("e2", "Odessa Port attacked", "2026-08-24T09:00:00+00:00", publisher="two.example", verification="curated_report"),
        ]
        episodes, *_ = converge_events(events, resolver=self.resolver, now=self.now)
        strength = episodes[0].evidence_strength
        self.assertIsNotNone(strength)
        assert strength is not None
        self.assertGreaterEqual(strength.overall_index, 0)
        self.assertLessEqual(strength.overall_index, 100)
        self.assertEqual("geowatch-evidence-strength-v0.5", strength.method_version)

    def test_sqlite_episode_lineage_roundtrip(self) -> None:
        events = [
            ev("db1", "Port of Odesa damaged after missile strike", "2026-08-24T08:00:00+00:00"),
            ev("db2", "Odessa Port halted operations following attack", "2026-08-24T09:00:00+00:00", publisher="two.example"),
        ]
        episodes, claims, evidence, entities, changes = converge_events(events, resolver=self.resolver, now=self.now)
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "geowatch.db")
            store.upsert_events(events)
            store.upsert_entities(entities)
            store.upsert_evidence(evidence)
            store.upsert_claims(claims)
            store.upsert_episodes(episodes)
            for change in changes:
                store.record_episode_change(change)
            loaded = store.load_episodes()
            self.assertEqual(1, len(loaded))
            self.assertEqual(set(episodes[0].event_ids), set(loaded[0].event_ids))
            self.assertEqual(len(claims), len(store.load_claims(episode_id=episodes[0].episode_id)))
            self.assertEqual(len(evidence), len(store.load_evidence(episode_id=episodes[0].episode_id)))
            store.close()


if __name__ == "__main__":
    unittest.main()

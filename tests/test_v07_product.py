from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from geowatch.alerts import AlertPolicy, enqueue_alerts, evaluate_alerts
from geowatch.consumers import build_consumer_feed, load_profile
from geowatch.convergence import converge_events
from geowatch.dashboard import dashboard_html, map_points
from geowatch.delivery import dispatch_pending
from geowatch.entities import EntityResolver
from geowatch.models import EvidenceStrength, Event
from geowatch.storage import SQLiteStore


def event(event_id: str, title: str, *, country: str = "Egypt", publisher: str = "one.example", impacts: tuple[str, ...] = ()) -> Event:
    return Event(
        event_id=event_id, source_id="test", source_kind="news", title=title, event_type="media_report",
        reference_at="2026-08-24T10:00:00+00:00", collected_at="2026-08-24T10:00:00+00:00",
        published_at="2026-08-24T10:00:00+00:00", verification_level="osint_signal",
        country=country, publisher=publisher, source_url=f"https://{publisher}/{event_id}",
        impact_areas=impacts,  # type: ignore[arg-type]
    )


class V07ProductTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = EntityResolver.from_json("config/entities.json")
        self.now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)

    def test_contradiction_policy_is_quiet_without_flag(self) -> None:
        episodes, *_ = converge_events([event("a1", "Routine humanitarian evacuation")], resolver=self.resolver, now=self.now)
        policy = AlertPolicy(policy_id="contradiction", severity="medium", required_flags=("contradiction_present",))
        self.assertEqual([], evaluate_alerts(episodes, [], [policy], created_at=self.now.isoformat()))

    def test_alert_outbox_deduplicates_same_episode_version(self) -> None:
        ev = event("a2", "Suez Canal blocked after attack", impacts=("shipping",))
        episodes, *_ = converge_events([ev], resolver=self.resolver, now=self.now)
        policy = AlertPolicy(policy_id="active", severity="high", states=(episodes[0].state,))
        alerts = evaluate_alerts(episodes, [], [policy], created_at=self.now.isoformat())
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "g.db")
            store.upsert_events([ev]); store.upsert_episodes(episodes)
            self.assertEqual(1, enqueue_alerts(store, alerts)); self.assertEqual(0, enqueue_alerts(store, alerts))
            store.close()

    def test_agrolog_profile_filters_humanitarian_only_episode(self) -> None:
        ev = event("h1", "Refugee evacuation and humanitarian displacement", country="Sudan", impacts=("humanitarian",))
        episodes, claims, evidence, entities, changes = converge_events([ev], resolver=self.resolver, now=self.now)
        episodes = [replace(episodes[0], evidence_strength=_strong())]
        with _store_with(Path, ev, episodes, claims, evidence, entities, changes) as store:
            feed = build_consumer_feed(store, load_profile("config/consumers/agrolog.json"))
            self.assertEqual([], feed["episodes"]); self.assertTrue(feed["read_only"])

    def test_agrolog_profile_includes_shipping_episode(self) -> None:
        ev = event("s1", "Suez Canal blocked and shipping disrupted", impacts=("shipping", "logistics"))
        episodes, claims, evidence, entities, changes = converge_events([ev], resolver=self.resolver, now=self.now)
        episodes = [replace(episodes[0], evidence_strength=_strong())]
        with _store_with(Path, ev, episodes, claims, evidence, entities, changes) as store:
            feed = build_consumer_feed(store, load_profile("config/consumers/agrolog.json"))
            self.assertEqual(1, len(feed["episodes"])); self.assertIn("shipping", feed["episodes"][0]["matching_impact_areas"])

    def test_map_points_use_resolved_infrastructure_coordinates(self) -> None:
        ev = event("m1", "Port of Odesa attacked", country="Ukraine")
        episodes, claims, evidence, entities, changes = converge_events([ev], resolver=self.resolver, now=self.now)
        with _store_with(Path, ev, episodes, claims, evidence, entities, changes) as store:
            points = map_points(store)
            self.assertEqual(1, len(points)); self.assertIsInstance(points[0]["latitude"], float)

    def test_dashboard_is_static_shell(self) -> None:
        html = dashboard_html()
        self.assertIn("maplibre", html.casefold())
        self.assertNotIn("leaflet", html.casefold())
        self.assertIn("/v2/map", html)
        self.assertIn("API bearer token", html)

    def test_dispatch_marks_webhook_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "g.db")
            store.enqueue_alert({"alert_id":"alt_test","episode_id":"ep_test","created_at":self.now.isoformat(),"severity":"high","policy_id":"test"})
            response = MagicMock()
            response.__enter__.return_value = response
            response.__exit__.return_value = False
            response.status = 204
            response.geturl.return_value = "https://example.invalid/hook"
            with patch("geowatch.delivery.urlopen", return_value=response):
                result = dispatch_pending(store, webhook_url="https://example.invalid/hook")
            self.assertEqual(1, result["delivered"]); self.assertEqual([], store.pending_alerts()); store.close()


def _strong() -> EvidenceStrength:
    return EvidenceStrength(provider_independence=1, research_coded=1, curated_institutional=1, sensor_context=0, geolocation=1, entity_resolution=1, recency=1, contradiction_penalty=0, overall_index=80)


class _store_with:
    def __init__(self, _path_type, ev, episodes, claims, evidence, entities, changes):
        self.tmp = tempfile.TemporaryDirectory(); self.store = SQLiteStore(Path(self.tmp.name) / "g.db")
        self.store.upsert_events([ev]); self.store.upsert_entities(entities); self.store.upsert_evidence(evidence); self.store.upsert_episodes(episodes); self.store.upsert_claims(claims); self.store.record_changes(changes)
    def __enter__(self): return self.store
    def __exit__(self, *args): self.store.close(); self.tmp.cleanup()


if __name__ == "__main__": unittest.main()

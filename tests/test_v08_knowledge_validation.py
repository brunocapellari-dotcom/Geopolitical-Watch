from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from geowatch.convergence import converge_events
from geowatch.entities import EntityResolver
from geowatch.episode_ops import build_split_plan, merge_episodes
from geowatch.episode_reports import build_episode_report
from geowatch.geopolitics import GeopoliticalKnowledge
from geowatch.models import EvidenceStrength, Event
from geowatch.review import build_review_queue
from geowatch.storage import SQLiteStore
from geowatch.validation import calibrate_binary_alerts, source_coverage_inventory


def _event(event_id: str, title: str, *, country: str = "Ukraine", publisher: str = "example.org") -> Event:
    return Event(
        event_id=event_id,
        source_id="test",
        source_kind="news",
        title=title,
        event_type="media_report",
        reference_at="2026-08-24T10:00:00+00:00",
        collected_at="2026-08-24T10:00:00+00:00",
        published_at="2026-08-24T10:00:00+00:00",
        verification_level="osint_signal",
        country=country,
        publisher=publisher,
        source_url=f"https://{publisher}/{event_id}",
        impact_areas=("shipping", "logistics"),
    )


class V08KnowledgeValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.knowledge = GeopoliticalKnowledge.from_files()
        self.resolver = EntityResolver.from_json("config/entities.json")
        self.now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)

    def test_context_is_explicitly_non_evidentiary(self) -> None:
        ev = _event("k1", "Suez Canal chokepoint blocked and maritime trade rerouted", country="Egypt")
        episodes, claims, evidence, entities, _ = converge_events([ev], resolver=self.resolver, now=self.now)
        context = self.knowledge.context_for_episode(episodes[0], claims=claims, entities=entities, events=[ev])
        ids = {row["id"] for row in context["matched_concepts"]}
        self.assertTrue(context["context_not_evidence"])
        self.assertIn("chokepoints", ids)
        self.assertTrue(context["analytical_questions"])

    def test_regional_context_and_historical_analogy_keep_limits(self) -> None:
        ev = _event("k2", "Ukraine alliance security guarantee and military buildup")
        episodes, claims, _, entities, _ = converge_events([ev], resolver=self.resolver, now=self.now)
        context = self.knowledge.context_for_episode(episodes[0], claims=claims, entities=entities, events=[ev])
        self.assertIn("europe_eurasia", {row["id"] for row in context["regional_context"]})
        for analogy in context["historical_analogies"]:
            self.assertIn("analogy_limits", analogy)

    def test_episode_report_embeds_strategic_context_without_changing_strength(self) -> None:
        ev = _event("k3", "Suez Canal chokepoint blocked after attack", country="Egypt")
        episodes, claims, evidence, entities, _ = converge_events([ev], resolver=self.resolver, now=self.now)
        before = episodes[0].evidence_strength.overall_index if episodes[0].evidence_strength else None
        report = build_episode_report(episodes, claims=claims, evidence=evidence, entities=entities, events=[ev], geopolitical_knowledge=self.knowledge)
        after = report["episodes"][0]["evidence_strength"]["overall_index"]
        self.assertEqual(before, after)
        self.assertTrue(report["episodes"][0]["strategic_context"]["context_not_evidence"])

    def test_review_queue_prioritizes_uncertain_episode(self) -> None:
        ev = _event("k4", "Unconfirmed military buildup near border")
        episodes, claims, evidence, _, _ = converge_events([ev], resolver=self.resolver, now=self.now)
        queue = build_review_queue(episodes, claims=claims, events=[ev], evidence=evidence)
        self.assertTrue(queue)
        self.assertIn(queue[0].priority, {"critical", "high", "medium", "low"})
        self.assertIn("emerging_episode", queue[0].reasons)

    def test_alert_calibration_metrics(self) -> None:
        result = calibrate_binary_alerts([
            {"predicted": True, "actual": True},
            {"predicted": True, "actual": False},
            {"predicted": False, "actual": True},
            {"predicted": False, "actual": False},
        ])
        self.assertEqual(0.5, result["precision"])
        self.assertEqual(0.5, result["recall"])
        self.assertEqual(0.5, result["false_positive_rate"])

    def test_merge_preserves_lineage_and_forces_recompute(self) -> None:
        ev1 = _event("k5a", "Port of Odesa attacked")
        ev2 = _event("k5b", "Odesa port strike reported", publisher="second.example")
        eps1, *_ = converge_events([ev1], resolver=self.resolver, now=self.now)
        eps2, *_ = converge_events([ev2], resolver=self.resolver, now=self.now)
        merged, lineage = merge_episodes([eps1[0], eps2[0]], occurred_at=self.now.isoformat(), reason="analyst_same_episode")
        self.assertIsNone(merged.evidence_strength)
        self.assertEqual(2, len(merged.event_ids))
        self.assertTrue(any(row["change_type"] == "episode_merge" for row in lineage))

    def test_split_plan_never_silently_reassigns_claims(self) -> None:
        ev1 = _event("k6a", "Port of Odesa attacked")
        ev2 = _event("k6b", "Rail corridor attacked")
        episodes, *_ = converge_events([ev1, ev2], resolver=self.resolver, now=self.now, attach_threshold=0.0)
        episode = replace(episodes[0], event_ids=(ev1.event_id, ev2.event_id))
        plan = build_split_plan(
            episode,
            event_groups=[(ev1.event_id,), (ev2.event_id,)],
            occurred_at=self.now.isoformat(),
            reason="analyst_distinct_events",
        )
        self.assertTrue(plan["safe_to_apply"])
        self.assertEqual(2, len(plan["children"]))
        self.assertIn("claims", plan["children"][0]["requires_recompute"])

    def test_source_coverage_inventory_uses_observed_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "g.db")
            store.record_run(
                run_id="r1", source_id="gdelt", started_at="2026-08-24T10:00:00+00:00",
                finished_at="2026-08-24T10:01:00+00:00", status="ok", records=10,
            )
            store.update_checkpoint("gdelt", last_success_at="2026-08-24T10:01:00+00:00", last_reference_at="2026-08-24T10:00:00+00:00")
            inventory = source_coverage_inventory(store)
            store.close()
        self.assertEqual(1, len(inventory["sources"]))
        self.assertEqual(10, inventory["sources"][0]["records"])
        self.assertEqual(1.0, inventory["sources"][0]["success_rate"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geowatch.episode_workflow import apply_merge, apply_split, revert_operation
from geowatch.escalation import EscalationLibrary
from geowatch.forecasting import forecast_summary
from geowatch.geoeconomics import chokepoint_exposure, concentration_hhi, dependency_score
from geowatch.hypotheses import make_hypothesis, score_hypotheses
from geowatch.learning import learning_policy, propose_from_review_decisions
from geowatch.maritime import active_notices, normalize_notice
from geowatch.models import ConflictEpisode, Event
from geowatch.sanctions import active_measures, normalize_sanction
from geowatch.strategic_graph import StrategicGraph
from geowatch.strategic_state import (
    list_forecasts, list_operations, list_review_decisions, record_forecast,
    record_review_decision, resolve_forecast,
)
from geowatch.storage import SQLiteStore


def _event(event_id: str, title: str, country: str = "Ukraine") -> Event:
    return Event(
        event_id=event_id, source_id="test", source_kind="news", title=title,
        event_type="media_report", reference_at="2026-08-24T10:00:00+00:00",
        collected_at="2026-08-24T10:00:00+00:00", published_at="2026-08-24T10:00:00+00:00",
        verification_level="osint_signal", country=country, publisher=f"{event_id}.example",
        source_url=f"https://{event_id}.example/report",
    )


def _episode(episode_id: str, event_id: str, title: str, country: str = "Ukraine") -> ConflictEpisode:
    return ConflictEpisode(
        episode_id=episode_id, title=title, state="emerging", started_at="2026-08-24T10:00:00+00:00",
        last_updated_at="2026-08-24T10:00:00+00:00", countries=(country,), regions=(),
        event_ids=(event_id,), claim_ids=(), evidence_ids=(),
    )


class V09StrategicIntelligenceTests(unittest.TestCase):
    def test_review_decision_and_learning_proposal_are_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "g.db")
            rows = []
            for index in range(2):
                rows.append(record_review_decision(
                    store, review_id=f"rev{index}", episode_id="ep1", decision="correct_entity",
                    rationale="confirmed alias mismatch", reviewer="analyst",
                    decided_at=f"2026-08-24T10:0{index}:00+00:00",
                    metadata={"knowledge_candidate": {"proposal_type":"alias_proposal", "subject_id":"entity_x", "alias":"example alias"}},
                ))
            self.assertEqual(2, len(list_review_decisions(store, episode_id="ep1")))
            proposals = propose_from_review_decisions(store, rows, min_support=2)
            self.assertEqual(1, len(proposals)); self.assertFalse(proposals[0]["payload"]["auto_apply"])
            self.assertFalse(learning_policy()["auto_mutate_knowledge"])
            store.close()

    def test_forecast_brier_and_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "g.db")
            f1 = record_forecast(store, subject_type="episode", subject_id="ep1", question="ceasefire within 30d", probability=0.8, horizon_at="2026-09-23T00:00:00+00:00", created_at="2026-08-24T10:00:00+00:00")
            f2 = record_forecast(store, subject_type="episode", subject_id="ep2", question="escalation within 30d", probability=0.3, horizon_at="2026-09-23T00:00:00+00:00", created_at="2026-08-24T10:01:00+00:00")
            resolve_forecast(store, f1["forecast_id"], outcome=True, resolved_at="2026-09-20T00:00:00+00:00")
            resolve_forecast(store, f2["forecast_id"], outcome=False, resolved_at="2026-09-20T00:00:00+00:00")
            summary = forecast_summary(list_forecasts(store))
            self.assertEqual(2, summary["resolved"])
            self.assertAlmostEqual(0.065, summary["brier_score"], places=6)
            self.assertTrue(summary["calibration"])
            store.close()

    def test_strategic_graph_profiles_and_sources(self):
        graph = StrategicGraph.from_files()
        japan = graph.country_profile("Japan")
        self.assertEqual("JPN", japan["country_id"])
        edges = graph.edges_for(["JPN"])
        self.assertTrue(any(row["relation"] == "security_alliance" for row in edges))
        self.assertTrue(graph.export_graph()["governance"]["edge_requires_source"])

    def test_escalation_indicators_are_not_probability(self):
        lib = EscalationLibrary.from_json()
        result = lib.detect(events=[_event("e1", "Ceasefire collapsed after port attacked")])
        self.assertTrue(result["indicator_score_not_probability"])
        self.assertGreater(result["escalation_points"], 0)
        self.assertTrue(any(row["id"] == "ceasefire_collapse" for row in result["indicators"]))

    def test_competing_hypotheses_remain_diagnostic(self):
        h1 = make_hypothesis("ep1", "deliberate escalation", indicators_for=("mobilization",), indicators_against=("withdrawal",))
        h2 = make_hypothesis("ep1", "precautionary signaling", indicators_for=("diplomatic_drawdown",), indicators_against=("cross_border_strike",))
        rows = score_hypotheses([h1, h2], ["mobilization"])
        self.assertEqual(h1.hypothesis_id, rows[0]["hypothesis_id"])
        self.assertTrue(rows[0]["score_not_probability"])

    def test_geoeconomic_dependency_metrics(self):
        self.assertAlmostEqual(0.5, concentration_hhi([50, 50]), places=6)
        metric = dependency_score(import_share_of_consumption=0.8, supplier_shares=(0.7, 0.3), route_shares=(0.9, 0.1), substitution_score=0.2)
        self.assertGreater(metric["dependency_index"], 0.5)
        route = chokepoint_exposure({"Hormuz": 0.6, "Other": 0.4}, ["Hormuz"])
        self.assertEqual(0.6, route["affected_route_share"])

    def test_sanctions_and_maritime_status_preserve_revocations(self):
        active = normalize_sanction(authority="test", regime="r", target_name="A", target_type="entity", measures=["asset_freeze"], effective_at="2026-01-01")
        revoked = normalize_sanction(authority="test", regime="r", target_name="B", target_type="entity", measures=["asset_freeze"], effective_at="2026-01-01", revoked_at="2026-02-01")
        self.assertEqual([active.sanction_id], [row.sanction_id for row in active_measures([active, revoked], as_of="2026-08-24")])
        notice = normalize_notice(authority="test", notice_type="NAVAREA", title="route closed", issued_at="2026-08-24T00:00:00Z", valid_to="2026-08-25T00:00:00Z")
        self.assertEqual(1, len(active_notices([notice], as_of="2026-08-24T12:00:00Z")))

    def test_merge_and_revert_preserve_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "g.db")
            e1, e2 = _event("m1", "Port Alpha attacked"), _event("m2", "Port Alpha damaged")
            ep1, ep2 = _episode("ep_a", "m1", e1.title), _episode("ep_b", "m2", e2.title)
            store.upsert_events([e1, e2]); store.upsert_episodes([ep1, ep2])
            result = apply_merge(store, ["ep_a", "ep_b"], survivor_id="ep_a", reason="analyst confirmed same episode", occurred_at="2026-08-24T12:00:00+00:00")
            self.assertEqual(2, len(store.get_episode("ep_a").event_ids))
            self.assertEqual("closed", store.get_episode("ep_b").state)
            revert_operation(store, result["operation"]["operation_id"], reason="review rollback", occurred_at="2026-08-24T13:00:00+00:00")
            self.assertEqual(("m1",), store.get_episode("ep_a").event_ids)
            self.assertEqual("emerging", store.get_episode("ep_b").state)
            self.assertGreaterEqual(len(list_operations(store)), 2)
            store.close()

    def test_split_and_revert_preserve_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "g.db")
            e1 = _event("s1", "Port of Odesa attacked")
            e2 = _event("s2", "Airport in Kyiv attacked")
            original = ConflictEpisode(
                episode_id="ep_split", title="Mixed reports", state="active", started_at="2026-08-24T10:00:00+00:00",
                last_updated_at="2026-08-24T10:00:00+00:00", countries=("Ukraine",), regions=(),
                event_ids=("s1", "s2"), claim_ids=(), evidence_ids=(),
            )
            store.upsert_events([e1, e2]); store.upsert_episodes([original])
            result = apply_split(store, "ep_split", event_groups=[["s1"], ["s2"]], reason="distinct locations", occurred_at="2026-08-24T12:00:00+00:00")
            self.assertEqual(2, len(result["children"]))
            self.assertEqual("closed", store.get_episode("ep_split").state)
            revert_operation(store, result["operation"]["operation_id"], reason="split rejected", occurred_at="2026-08-24T13:00:00+00:00")
            self.assertEqual(("s1", "s2"), store.get_episode("ep_split").event_ids)
            self.assertEqual("active", store.get_episode("ep_split").state)
            store.close()


if __name__ == "__main__":
    unittest.main()

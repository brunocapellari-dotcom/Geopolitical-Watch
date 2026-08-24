from __future__ import annotations

import unittest

from geowatch.actor_profiles import ActorProfiles
from geowatch.chokepoints import route_exposure
from geowatch.critical_infrastructure import CriticalInfrastructureGraph
from geowatch.forecast_templates import ForecastTemplates, monotonicity_flags
from geowatch.geoeconomic_observations import GeoeconomicObservation, bilateral_concentration
from geowatch.global_profiles import GlobalProfileRegistry
from geowatch.historical_backtest import evaluate_temporal_backtest
from geowatch.historical_corpus import HistoricalCorpus
from geowatch.leading_indicators import LeadingIndicators, lead_time_stats
from geowatch.maritime_feed import parse_json_feed
from geowatch.postmortem import build_postmortem, learning_proposals
from geowatch.readiness import ReadinessModel, current_code_readiness_estimate
from geowatch.sanctions_feed import parse_un_consolidated_xml
from geowatch.security_systems import SecuritySystems


class V10EmpiricalIntelligenceTests(unittest.TestCase):
    def test_global_country_registry_has_world_coverage(self):
        registry=GlobalProfileRegistry.from_files(); coverage=registry.coverage()
        self.assertGreaterEqual(coverage["registry_count"],240)
        self.assertTrue(registry.profile("BRA")["context_not_evidence"])
        self.assertIn(registry.profile("AFG")["profile_status"],{"enriched","baseline_needs_enrichment"})

    def test_actor_profiles_are_context_only(self):
        actors=ActorProfiles.from_json(); row=actors.profile("UN")
        self.assertEqual("United Nations",row["name"]); self.assertTrue(row["context_not_evidence"])

    def test_security_system_distinguishes_partnership(self):
        systems=SecuritySystems.from_json(); usa=systems.memberships("USA")
        kinds={row["relationship_type"] for row in usa}
        self.assertIn("collective_defence_alliance",kinds); self.assertIn("strategic_dialogue",kinds)

    def test_critical_infrastructure_graph(self):
        graph=CriticalInfrastructureGraph.from_json(); summary=graph.summary()
        self.assertGreaterEqual(summary["node_count"],20)
        self.assertEqual(["STRAIT_HORMUZ","BAB_EL_MANDEB","SUEZ_CANAL"],graph.shortest_context_path("STRAIT_HORMUZ","SUEZ_CANAL"))

    def test_geoeconomic_observation_concentration(self):
        rows=[
            GeoeconomicObservation("1","official","2025","2026-01-01","2026-01-02","BRA","CHN","soy",70,"USD"),
            GeoeconomicObservation("2","official","2025","2026-01-01","2026-01-02","BRA","EU","soy",30,"USD"),
        ]
        result=bilateral_concentration(rows,origin="BRA",commodity="soy")
        self.assertAlmostEqual(0.58,result["hhi"],places=2)

    def test_chokepoint_exposure_is_not_loss_forecast(self):
        result=route_exposure({"STRAIT_HORMUZ":0.6,"CAPE_GOOD_HOPE":0.4},disrupted_nodes=["STRAIT_HORMUZ"],alternatives={"STRAIT_HORMUZ":["CAPE_GOOD_HOPE"]})
        self.assertAlmostEqual(0.6,result["affected_route_share"]); self.assertTrue(result["structural_exposure_not_loss_forecast"])

    def test_un_sanctions_xml_parser(self):
        xml=b'<ROOT><INDIVIDUAL><DATAID>1</DATAID><FIRST_NAME>Example</FIRST_NAME><SECOND_NAME>Person</SECOND_NAME><UN_LIST_TYPE>Test</UN_LIST_TYPE><LISTED_ON>2026-01-01</LISTED_ON></INDIVIDUAL></ROOT>'
        rows=parse_un_consolidated_xml(xml,collected_at="2026-08-24T12:00:00+00:00")
        self.assertEqual(1,len(rows)); self.assertEqual("UNSC",rows[0].authority); self.assertEqual("Example Person",rows[0].name)

    def test_maritime_warning_normalization(self):
        payload=b'{"warnings":[{"id":"1","navarea":"III","title":"TEST WARNING","body":"navigation caution","latitude":35,"longitude":20}]}'
        rows=parse_json_feed(payload,authority="NAVAREA III",collected_at="2026-08-24T12:00:00+00:00")
        self.assertEqual(1,len(rows)); self.assertTrue(rows[0].warning_scope_only)

    def test_multi_horizon_templates(self):
        templates=ForecastTemplates.from_json()
        rows=templates.instantiate("ceasefire",episode_id="ep1",created_at="2026-08-24T12:00:00+00:00",probabilities={7:0.2,30:0.4,90:0.6})
        self.assertEqual([7,30,90],[row["horizon_days"] for row in rows]); self.assertEqual([],monotonicity_flags(rows))

    def test_backtest_rejects_lookahead(self):
        rows=[{"forecast_id":"ok","created_at":"2020-01-01T00:00:00+00:00","resolved_at":"2020-02-01T00:00:00+00:00","information_cutoff":"2020-01-01T00:00:00+00:00","probability":0.7,"outcome":1,"horizon_days":30},{"forecast_id":"bad","created_at":"2020-03-01T00:00:00+00:00","resolved_at":"2020-02-01T00:00:00+00:00","information_cutoff":"2020-03-01T00:00:00+00:00","probability":0.7,"outcome":1,"horizon_days":30}]
        result=evaluate_temporal_backtest(rows)
        self.assertEqual(1,result["accepted"]); self.assertEqual(1,result["rejected"])

    def test_leading_indicator_lead_time(self):
        lib=LeadingIndicators.from_json(); self.assertIsNotNone(lib.definition("reserve_callup"))
        stats=lead_time_stats([{"indicator_id":"reserve_callup","observed_at":"2026-01-01T00:00:00+00:00","outcome_id":"o1"}],[{"outcome_id":"o1","resolved_at":"2026-01-02T00:00:00+00:00"}])
        self.assertEqual(24.0,stats["indicators"][0]["mean_lead_hours"])

    def test_historical_corpus_hides_future_outcomes(self):
        corpus=HistoricalCorpus.from_json(); self.assertGreaterEqual(corpus.summary()["case_count"],40)
        rows={row["case_id"]:row for row in corpus.as_of("1962-10-20")}
        self.assertTrue(rows["cuba_missile_1962"]["outcome_hidden_due_to_cutoff"])

    def test_postmortem_generates_nonautomatic_proposal(self):
        pm=build_postmortem(subject_type="episode",subject_id="ep1",created_at="2026-08-24T12:00:00+00:00",initial_thesis="test",available_evidence_ids=["e1"],forecast_ids=["f1"],observed_outcome="no escalation",error_class="base_rate_neglect",causal_review=["overweighted one signal"],method_changes=["add base-rate check"])
        proposals=learning_proposals(pm); self.assertEqual(1,len(proposals)); self.assertFalse(proposals[0]["auto_apply"])

    def test_readiness_requires_hard_gates(self):
        model=ReadinessModel.from_json(); scores={row["id"]:1 for row in model.payload["dimensions"]}; gates={gate:False for gate in model.payload["hard_gates"]}
        result=model.evaluate(scores,gates); self.assertEqual(1.0,result["weighted_readiness"]); self.assertFalse(result["target_reached"])

    def test_current_readiness_is_conservative(self):
        result=current_code_readiness_estimate(); self.assertLess(result["weighted_readiness"],0.95); self.assertFalse(result["all_hard_gates_passed"])


if __name__=="__main__": unittest.main()

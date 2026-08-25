from __future__ import annotations

import unittest

from geowatch.human_gold import binary_review_metrics,calibration_segments,make_review_batch,validate_reviewed_batch
from geowatch.infrastructure_promotion import corroborate_ports
from geowatch.learning_governance import leading_indicator_metrics,postmortem_gate
from geowatch.prospective_forecasting import append_forecast_ledger,create_prospective_forecasts,resolve_forecasts,score_resolved_forecasts
from geowatch.source_failover import build_failover_plan
from geowatch.source_resilience import append_source_history,circuit_breaker,summarize_source_history
from geowatch.strategic_flows import dependency_metrics


class V014LearningResilienceTests(unittest.TestCase):
    def test_source_resilience_tracks_availability_mttr_and_slo(self):
        history=None
        history=append_source_history(history,generated_at="2026-08-25T00:00:00+00:00",source_results=[{"source_id":"s","status":"error","error":"HTTP Error 503"}],coverage={})
        history=append_source_history(history,generated_at="2026-08-25T01:00:00+00:00",source_results=[{"source_id":"s","status":"ok"}],coverage={"sources":[{"source_id":"s","last_reference_in_bounded_sample":"2026-08-25T00:30:00+00:00"}]})
        summary=summarize_source_history(history,as_of="2026-08-25T02:00:00+00:00",slo_config={"sources":[{"source_id":"s","max_freshness_hours":3,"monthly_availability_target":0.5}]})
        row=summary["sources"][0]
        self.assertEqual(0.5,row["availability_ratio"]); self.assertEqual(60.0,row["mttr_minutes"]); self.assertTrue(row["freshness_slo_passed"])

    def test_circuit_breaker_opens_after_consecutive_transient_failures(self):
        obs=[{"source_id":"s","observed_at":f"2026-08-25T0{i}:00:00+00:00","result_class":"transient_failure"} for i in range(3)]
        decision=circuit_breaker("s",obs,now="2026-08-25T02:05:00+00:00",failure_threshold=3,cooldown_seconds=900)
        self.assertEqual("open",decision.state); self.assertFalse(decision.allow_request)

    def test_failover_does_not_fake_independent_corroboration(self):
        plan=build_failover_plan("gdelt_conflict_news","HTTP 429",{"sources":[{"source_id":"gdelt_conflict_news","transient_steps":[{"action":"reduce_query_load","same_provider":True}]}]})
        self.assertEqual(0,plan["independent_corroboration_count"]); self.assertTrue(plan["same_provider_fallback_never_counts_as_independent_corroboration"])

    def test_human_gold_requires_reviewer_and_timestamp(self):
        batch=make_review_batch([{"candidate_id":"c1","task_type":"episode_merge_split","review_status":"unreviewed"}],batch_id="b1")
        invalid=validate_reviewed_batch(batch); self.assertEqual(0,invalid["accepted_count"])
        row=batch["items"][0]; row.update({"human_label":"separate","reviewer":"analyst","reviewed_at":"2026-08-25T10:00:00Z"})
        valid=validate_reviewed_batch(batch); self.assertEqual(1,valid["accepted_count"]); self.assertTrue(valid["accepted"][0]["human_gold"])

    def test_gold_metrics_and_calibration_are_sample_gated(self):
        rows=[{"task_type":"conflict_vs_context","human_gold":True,"human_label":"context","machine_label":"conflict","machine_score":0.7,"region":"R","source_mix":["a","b"]}]
        metrics=binary_review_metrics(rows,task_type="conflict_vs_context",positive_label="conflict"); self.assertEqual(1.0,metrics["false_positive_rate"])
        segment=calibration_segments(rows,min_samples=30)["segments"][0]; self.assertFalse(segment["eligible_for_threshold_calibration"])

    def test_prospective_forecasts_are_append_only_and_scored(self):
        forecasts=create_prospective_forecasts([{"episode_id":"e1","state":"active","evidence_strength":{"overall_index":50}}],created_at="2026-08-25T00:00:00+00:00")
        ledger=append_forecast_ledger(None,forecasts); before={r["forecast_id"]:r["probability"] for r in ledger["forecasts"]}
        ledger=resolve_forecasts(ledger,{"e1":{"state":"escalating"}},resolved_at="2026-08-25T12:00:00+00:00")
        after={r["forecast_id"]:r["probability"] for r in ledger["forecasts"]}; self.assertEqual(before,after)
        self.assertGreater(score_resolved_forecasts(ledger)["resolved_count"],0)

    def test_leading_indicator_metrics_keep_false_positives(self):
        result=leading_indicator_metrics([{"episode_id":"e1","signal_type":"x","observed_at":"2026-08-01T00:00:00Z"},{"episode_id":"e2","signal_type":"x","observed_at":"2026-08-01T00:00:00Z"}],[{"episode_id":"e1","outcome_type":"escalation","observed_at":"2026-08-03T00:00:00Z"}])
        self.assertEqual(0.5,result["false_positive_rate"]); self.assertEqual(2.0,result["mean_lead_days"])

    def test_postmortem_gate_blocks_material_missing_reviews(self):
        gate=postmortem_gate([{"incident_id":"i1","severity":"high"}],[]); self.assertFalse(gate["passed"])

    def test_port_identity_does_not_equal_criticality(self):
        wpi=[{"port_name":"Port X","country":"AA"}]; loc=[{"location_name":"Port X","country":"AA"}]
        result=corroborate_ports(wpi,loc); self.assertEqual("identity_corroborated",result["nodes"][0]["status"])
        result=corroborate_ports(wpi,loc,[{"port_name":"Port X","country":"AA","evidence_type":"official_chokepoint"}]); self.assertEqual("reviewed_critical",result["nodes"][0]["status"])

    def test_dependency_metrics_keep_missing_unknown(self):
        rows=[{"source_id":"u","reference_period":"2025","reporter":"A","partner":"B","flow":"imports","domain":"energy","value":80,"unit":"USD"},{"source_id":"u","reference_period":"2025","reporter":"A","partner":"C","flow":"imports","domain":"energy","value":20,"unit":"USD"},{"source_id":"u","reference_period":"2025","reporter":"A","partner":"D","flow":"imports","domain":"energy","value":None,"unit":"USD"}]
        result=dependency_metrics(rows,reporter="A",domain="energy"); self.assertEqual(0.8,result["periods"][0]["top1_share"])


if __name__=="__main__": unittest.main()

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geowatch.forecast_evaluation import brier_skill,forecast_miss_postmortems,reliability_diagram
from geowatch.gold_calibration import deterministic_gold_split,evaluate_holdout,threshold_scan
from geowatch.human_review_workflow import adjudication_queue,finalize_gold,inter_rater_agreement,render_review_html
from geowatch.knowledge_release import compare_knowledge_manifests,incident_note,release_note
from geowatch.slo_analytics import burn_rate,error_budget,reliability_score,stale_coverage_alerts
from geowatch.slo_dashboard import build_slo_dashboard
from geowatch.sources import eia_international,faostat,usgs_mcs


class V015EmpiricalCalibrationTests(unittest.TestCase):
    def test_error_budget_and_burn_rate_are_operational(self):
        budget=error_budget(availability_target=0.95,observed_availability=0.90)
        self.assertAlmostEqual(2.0,budget["budget_consumed_ratio"])
        obs=[{"source_id":"s","observed_at":"2026-08-25T00:00:00Z","result_class":"success"},{"source_id":"s","observed_at":"2026-08-25T01:00:00Z","result_class":"transient_failure"}]
        burn=burn_rate(obs,source_id="s",availability_target=0.95,as_of="2026-08-25T02:00:00Z")
        self.assertGreater(burn["short_window"]["burn_rate"],1)
        rel=reliability_score(availability_30d=0.98,freshness_slo_passed=True,open_incident=False)
        self.assertTrue(rel["operational_not_intelligence_quality"])

    def test_stale_alert_and_dashboard_do_not_claim_accuracy(self):
        summary={"as_of":"2026-08-25T10:00:00Z","sources":[{"source_id":"s","rolling_availability":{"7":{"availability_ratio":1},"30":{"availability_ratio":1},"90":{"availability_ratio":1}},"freshness_hours":8,"freshness_slo_passed":False,"mttr_minutes":10,"open_incident":False}]}
        cfg={"sources":[{"source_id":"s","max_freshness_hours":3,"monthly_availability_target":0.95}]}
        alerts=stale_coverage_alerts(summary,cfg); self.assertEqual("stale_coverage",alerts[0]["alert_type"]); self.assertFalse(alerts[0]["event_evidence"])
        dash=build_slo_dashboard(summary,cfg); self.assertTrue(dash["operational_metrics_not_intelligence_accuracy"])

    def test_dual_review_requires_adjudication_on_disagreement(self):
        reviews=[
            {"candidate_id":"c1","task_type":"conflict_vs_context","human_label":"conflict","reviewer":"A","reviewed_at":"2026-08-25T10:00:00Z"},
            {"candidate_id":"c1","task_type":"conflict_vs_context","human_label":"context","reviewer":"B","reviewed_at":"2026-08-25T10:01:00Z"},
        ]
        agreement=inter_rater_agreement(reviews); self.assertEqual(0.0,agreement["pairwise_agreement"])
        queue=adjudication_queue(reviews); self.assertEqual(1,queue["count"])
        gold=finalize_gold(reviews); self.assertEqual(0,gold["count"]); self.assertIn("c1",gold["blocked_disagreements"])
        adjud=[{"candidate_id":"c1","adjudicated_label":"conflict","adjudicator":"C","adjudicated_at":"2026-08-25T11:00:00Z"}]
        gold=finalize_gold(reviews,adjud); self.assertEqual(1,gold["count"]); self.assertEqual("adjudicated",gold["items"][0]["gold_method"])

    def test_review_html_is_explicitly_not_gold(self):
        batch={"items":[{"candidate_id":"c1","task_type":"episode_merge_split","title":"Case"}]}
        page=render_review_html(batch); self.assertIn("not gold",page); self.assertIn("Human label",page)

    def test_gold_split_is_deterministic_and_holdout_separate(self):
        rows=[{"candidate_id":f"c{i}","human_gold":True,"human_label":"merge" if i%2 else "separate","machine_score":i/100} for i in range(100)]
        a=deterministic_gold_split(rows); b=deterministic_gold_split(rows)
        self.assertEqual([r["candidate_id"] for r in a["holdout"]],[r["candidate_id"] for r in b["holdout"]])
        scan=threshold_scan(a["train"],positive_label="merge"); self.assertTrue(scan["threshold_not_auto_promoted"])
        if scan["best"] and a["holdout"]:
            result=evaluate_holdout(a["holdout"],positive_label="merge",threshold=scan["best"]["threshold"]); self.assertTrue(result["holdout_only"])

    def test_forecast_skill_and_postmortems_use_resolved_rows_only(self):
        rows=[
            {"forecast_id":"a","episode_id":"e","status":"resolved","probability":0.9,"observed_outcome":0,"resolved_at":"2026-08-25T10:00:00Z","information_cutoff":"2026-08-24T10:00:00Z","outcome":"escalation"},
            {"forecast_id":"b","episode_id":"e","status":"resolved","probability":0.2,"observed_outcome":0,"resolved_at":"2026-08-25T10:00:00Z","information_cutoff":"2026-08-24T10:00:00Z","outcome":"ceasefire"},
            {"forecast_id":"c","status":"open","probability":0.9,"observed_outcome":1},
        ]
        diag=reliability_diagram(rows); self.assertEqual(2,diag["resolved_count"])
        skill=brier_skill(rows); self.assertEqual(2,skill["count"])
        posts=forecast_miss_postmortems(rows,threshold=0.65); self.assertEqual(1,len(posts)); self.assertTrue(posts[0]["automatic_model_change_forbidden"])

    def test_faostat_preserves_quality_flag(self):
        payload=b"Area,Item,Element,Year,Unit,Value,Flag\nBrazil,Soybeans,Production,2024,t,1000,E\n"
        rows=faostat.parse_csv(payload,dataset_id="x",collected_at="2026-08-25T10:00:00Z")
        self.assertEqual("E",rows[0]["flag"]); self.assertTrue(rows[0]["quality_flag_preserved"])

    def test_usgs_parser_preserves_reference_fields(self):
        payload=b"Commodity,Country,Year,Production,Unit\nLithium,Chile,2025,50000,t\n"
        rows=usgs_mcs.parse_csv(payload,file_name="x.csv",collected_at="2026-08-25T10:00:00Z")
        self.assertEqual("Lithium",rows[0]["commodity"]); self.assertEqual(50000.0,rows[0]["value"])

    def test_eia_bulk_manifest_and_api_key_gate(self):
        manifest={"International":{"identifier":"International","title":"International energy data"},"Other":{"identifier":"foo"}}
        rows=eia_international.international_bulk_entries(manifest); self.assertEqual(1,len(rows))
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(eia_international.activation_status()["api_key_present"])
            with self.assertRaises(RuntimeError): eia_international.api_query("international/data")

    def test_knowledge_drift_and_notes(self):
        expected={"notes":[{"file":"a.md","sha256":"1"},{"file":"b.md","sha256":"2"}]}; mirror={"notes":[{"file":"a.md","sha256":"1"},{"file":"b.md","sha256":"3"}]}
        drift=compare_knowledge_manifests(expected,mirror); self.assertTrue(drift["drift"]); self.assertEqual(["b.md"],drift["changed"])
        rel=release_note(version="0.15.0",merge_commit="abc",released_at="2026-08-25T10:00:00Z",gates=[{"name":"tests","conclusion":"success"}],capabilities=["x"],hard_gates_open=["gcp"]); self.assertIn("Release v0.15.0",rel); self.assertIn("gcp",rel)
        inc=incident_note({"incident_id":"i1","incident_type":"provider_outage","severity":"high","detected_at":"2026-08-25T10:00:00Z","expected_behavior":"ok","observed_behavior":"503","evidence":[]}); self.assertIn("Incident i1",inc)


if __name__=="__main__": unittest.main()

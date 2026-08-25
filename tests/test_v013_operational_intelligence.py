from __future__ import annotations

import unittest
from datetime import date,timedelta

from geowatch.actor_profiles import ActorProfiles
from geowatch.geoeconomic_context import dependency_matrix
from geowatch.historical_validation_assets import build_chronologies,build_gold_review_candidates,build_frozen_forecast_bank,summarize_forecast_bank
from geowatch.infrastructure_review import review_wpi_candidates
from geowatch.operational_intelligence import append_history,build_operational_snapshot,compare_snapshots
from geowatch.profile_enrichment import ProfileEnrichmentQueue
from geowatch.readiness import current_code_readiness_estimate
from geowatch.rolling_validation import rolling_oos_report
from geowatch.scenario_catalog import ScenarioCatalog


class V013OperationalIntelligenceTests(unittest.TestCase):
    def test_operational_snapshot_delta_and_history(self):
        coverage={"sources":[{"source_id":"gdelt_conflict_news","last_run_status":"ok","last_reference_in_bounded_sample":None}]}
        ep={"episodes":[{"episode_id":"e1","title":"A","state":"active","countries":["X"],"last_updated_at":"2026-08-25T00:00:00+00:00","change_flags":[],"evidence_strength":{"overall_index":40}}]}
        first=build_operational_snapshot(generated_at="2026-08-25T00:00:00+00:00",source_results=[{"source_id":"gdelt_conflict_news","status":"ok"}],coverage=coverage,episode_report=ep)
        ep["episodes"][0]["state"]="escalating"; ep["episodes"][0]["evidence_strength"]["overall_index"]=50
        second=build_operational_snapshot(generated_at="2026-08-25T01:00:00+00:00",source_results=[{"source_id":"gdelt_conflict_news","status":"ok"}],coverage=coverage,episode_report=ep)
        delta=compare_snapshots(first,second)
        self.assertTrue(any(r["type"]=="state_changed" for r in delta["changes"]))
        self.assertTrue(any(r["type"]=="evidence_strength_shift" for r in delta["changes"]))
        self.assertEqual(2,append_history(append_history(None,first),second)["snapshot_count"])

    def _cases(self):
        cases=[]; start=date(1950,1,1)
        for i in range(180):
            s=start+timedelta(days=i*400); e=s+timedelta(days=60+(i%100))
            cases.append({"case_id":f"c{i}","ucdp_conflict_id":str(i//2),"ucdp_episode_no":i%2+1,"start":s.isoformat(),"end":e.isoformat(),"active_years":[s.year],"actors":["A","B"],"region":"R1" if i%2==0 else "R2","location":"L","outcome_tags":["ceasefire"] if i%3==0 else ["peace_agreement"],"source_ids":["ucdp_prio_acd_26_1","ucdp_termination_4_2024"]})
        return cases

    def test_historical_assets_reach_targets_without_fake_gold(self):
        cases=self._cases(); self.assertEqual(150,len(build_chronologies(cases,limit=150)))
        gold=build_gold_review_candidates(cases,limit=500); self.assertTrue(gold and not any(r["human_gold"] for r in gold))
        bank=build_frozen_forecast_bank(cases,limit=240); self.assertGreaterEqual(len(bank),200)
        summary=summarize_forecast_bank(bank); self.assertEqual({1,7,30,90},{int(k) for k in summary["by_horizon"]})

    def test_rolling_oos_exposes_year_region_and_source_mix(self):
        bank=build_frozen_forecast_bank(self._cases(),limit=240)
        rows=[{"forecast_id":r["forecast_id"],"probability":r["baseline_probability"],"outcome":int(r["observed_outcome"]),"created_at":r["created_at"],"information_cutoff":r["information_cutoff"],"resolved_at":r["resolved_at"],"horizon_days":r["horizon_days"],"region":r["region"],"source_mix":r["source_mix"]} for r in bank]
        report=rolling_oos_report(forecasts=rows)
        self.assertGreaterEqual(report["forecast_backtest"]["accepted"],200)
        self.assertGreaterEqual(len(report["by_region"]["forecasts"]),2)
        self.assertGreaterEqual(len(report["by_source_mix"]["forecasts"]),1)
        self.assertTrue(report["windows"])

    def test_tier2_profiles_and_actor_targets(self):
        progress=ProfileEnrichmentQueue.from_files().progress(); tier2=next(r for r in progress["tiers"] if r["tier"]==2)
        self.assertGreaterEqual(tier2["ratio"],0.8); self.assertGreaterEqual(ActorProfiles.from_json().coverage()["profile_count"],50)

    def test_scenario_catalog_has_core_five(self):
        cat=ScenarioCatalog.from_json(); self.assertGreaterEqual(cat.summary()["scenario_count"],5)
        for sid in ("hormuz_disruption","bab_el_mandeb_suez_disruption","malacca_disruption","panama_disruption","turkish_straits_disruption"): self.assertIsNotNone(cat.get(sid))

    def test_wpi_single_source_does_not_fake_reviewed_critical(self):
        payload=review_wpi_candidates([{"port_name":"X","harbor_size":"Large","facilities":["Container","Oil Terminal"],"source_ids":["nga_wpi"]}])
        self.assertEqual(1,payload["review_ready_count"]); self.assertEqual(0,payload["reviewed_critical_count"])

    def test_geoeconomic_missing_is_not_zero_filled(self):
        matrix=dependency_matrix([{"reference_period":"2025","source_id":"x","origin":"A","destination":"B","commodity":"oil","value":10,"unit":"usd"},{"reference_period":"2025","source_id":"x","origin":"A","destination":"C","commodity":"oil","value":None,"unit":"usd"}],commodity="oil")
        self.assertEqual(1,matrix["edge_count"]); self.assertTrue(matrix["missing_data_not_zero_filled"])

    def test_readiness_stays_below_target_without_hard_gates(self):
        result=current_code_readiness_estimate(); self.assertGreaterEqual(result["weighted_readiness"],0.85); self.assertFalse(result["target_reached"]); self.assertFalse(result["all_hard_gates_passed"])


if __name__=="__main__": unittest.main()

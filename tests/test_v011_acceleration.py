from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geowatch.backfill_planner import BackfillPlanner
from geowatch.critical_infrastructure import CriticalInfrastructureGraph
from geowatch.global_profiles import GlobalProfileRegistry
from geowatch.graph_audit import audit_strategic_graph
from geowatch.historical_corpus import HistoricalCorpus
from geowatch.profile_enrichment import ProfileEnrichmentQueue
from geowatch.reconciliation import reconcile
from geowatch.release_audit import ReleaseAudit
from geowatch.rolling_validation import rolling_oos_report
from geowatch.sanctions_feed import parse_uk_csv
from geowatch.source_activation import SourceActivationRegistry
from geowatch.sources import reliefweb
from geowatch.models import Event


class V011AccelerationTests(unittest.TestCase):
    def test_source_activation_is_source_scoped(self):
        registry=SourceActivationRegistry.from_json()
        status=registry.evaluate(env={},reviewed_terms=set())
        self.assertIn("gdelt_conflict_news",status["ready_sources"])
        self.assertIn("ucdp_ged_26_1",status["blocked_sources"])
        self.assertTrue(status["single_source_block_does_not_block_pipeline"])

    def test_backfill_queue_skips_blocked_restricted_sources(self):
        activation=SourceActivationRegistry.from_json().evaluate(env={},reviewed_terms=set())
        rows=BackfillPlanner.from_json().queue(activation,per_source_limit=1)
        ids={row["source_id"] for row in rows}
        self.assertIn("gdelt_conflict_news",ids); self.assertNotIn("ucdp_ged_26_1",ids)

    def test_reliefweb_window_uses_range_filter_and_offset(self):
        payload=json.dumps({"data":[]}).encode()
        class R:
            def __init__(self): self.payload=payload; self.url="https://example.test"
        with patch("geowatch.sources.reliefweb.get",return_value=R()) as mocked:
            pages,_=reliefweb.collect_window(start="2026-01-01T00:00:00+00:00",end="2026-01-02T00:00:00+00:00",appname="approved-test",limit=100)
        self.assertEqual(1,len(pages)); query=mocked.call_args.kwargs["query"]
        self.assertEqual("date.created",query["filter[field]"]); self.assertEqual(0,query["offset"])

    def test_firms_regions_are_not_world(self):
        payload=json.loads(Path("config/operations/firms_regions.json").read_text())
        self.assertFalse(payload["governance"]["world_area_for_production"])
        self.assertGreaterEqual(len(payload["areas"]),8)
        self.assertTrue(all(row["bbox"]!="world" for row in payload["areas"]))

    def test_cross_source_reconciliation_preserves_divergence(self):
        a=Event(event_id="u1",source_id="ucdp",source_kind="research",title="Actor A - Actor B",event_type="state_based_violence",reference_at="2026-08-20T00:00:00+00:00",collected_at="2026-08-21T00:00:00+00:00",verification_level="research_coded",country="Ukraine",latitude=46.48,longitude=30.73,actors=("Actor A","Actor B"))
        b=Event(event_id="a1",source_id="acled",source_kind="research",title="Armed clash between Actor A and Actor B",event_type="Battles",reference_at="2026-08-20T06:00:00+00:00",collected_at="2026-08-21T00:00:00+00:00",verification_level="research_coded",country="Ukraine",latitude=46.50,longitude=30.75,actors=("Actor A","Actor B"))
        result=reconcile([a],[b],threshold=0.4)
        self.assertEqual(1,len(result["matches"])); self.assertTrue(result["divergence_is_not_automatically_error"])

    def test_uk_sanctions_csv_normalization(self):
        csv=b"Unique ID,Name,Regime Name,Type,Date Designated\nUK001,Example Entity,Russia,Entity,2026-08-01\n"
        rows=parse_uk_csv(csv,collected_at="2026-08-24T00:00:00+00:00")
        self.assertEqual(1,len(rows)); self.assertEqual("UK-FCDO",rows[0].authority); self.assertEqual(("Russia",),rows[0].programs)

    def test_release_audit_keeps_external_gates_hard(self):
        audit=ReleaseAudit.from_files().evaluate(enabled_sources={"gdelt_conflict_news","unsc_sanctions"},evidence={})
        self.assertFalse(audit["passed"]); self.assertFalse(audit["gates"]["production_smoke"])

    def test_tier_one_profile_enrichment_accelerated(self):
        registry=GlobalProfileRegistry.from_files(); coverage=registry.coverage()
        self.assertGreaterEqual(coverage["enriched_count"],25)
        progress=ProfileEnrichmentQueue.from_files().progress()
        tier1=next(row for row in progress["tiers"] if row["tier"]==1)
        self.assertGreaterEqual(tier1["ratio"],0.95)

    def test_critical_infrastructure_expanded(self):
        graph=CriticalInfrastructureGraph.from_json(); summary=graph.summary()
        self.assertGreaterEqual(summary["node_count"],50)
        self.assertIsNotNone(graph.node("PORT_FUJAIRAH")); self.assertIsNotNone(graph.node("SEA_ME_WE_CABLE_CORRIDOR"))

    def test_historical_corpus_expanded_without_lookahead(self):
        corpus=HistoricalCorpus.from_json(); summary=corpus.summary()
        self.assertGreaterEqual(summary["case_count"],75)
        early={row["case_id"]:row for row in corpus.as_of("1962-10-20")}
        self.assertEqual([],early["cuba_missile_1962"]["outcome_tags"])

    def test_strategic_graph_integrity(self):
        result=audit_strategic_graph(); self.assertTrue(result["passed"],result["errors"])

    def test_rolling_oos_reports_unstable_windows_separately(self):
        forecasts=[{"forecast_id":"f1","created_at":"2024-01-01T00:00:00+00:00","resolved_at":"2024-02-01T00:00:00+00:00","information_cutoff":"2024-01-01T00:00:00+00:00","probability":0.8,"outcome":1,"horizon_days":30}]
        alerts=[{"at":"2024-01-02","predicted":True,"observed":True},{"at":"2025-01-02","predicted":True,"observed":False}]
        result=rolling_oos_report(forecasts=forecasts,alerts=alerts)
        self.assertEqual(2,len(result["windows"])); self.assertEqual(0.5,result["overall_alerts"]["precision"])


if __name__ == "__main__": unittest.main()

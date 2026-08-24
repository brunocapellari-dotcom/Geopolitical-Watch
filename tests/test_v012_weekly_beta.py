from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from geowatch.alert_eval import classification_metrics, evaluate_alert_labels
from geowatch.chokepoint_scenario_pack import build_scenario_pack
from geowatch.coverage_dashboard import build_source_coverage_dashboard
from geowatch.historical_forecast_baseline import baseline_summary, build_base_rate_forecasts
from geowatch.models import Event
from geowatch.sanctions_graph import build_entity_name_index, link_designations
from geowatch.storage import SQLiteStore
from geowatch.ucdp_bulk import aggregate_armed_conflict_cases, read_zip_csv
from geowatch.ucdp_labels import derive_conflict_identity_labels, label_summary
from geowatch.worldbank import latest_by_country
from geowatch.wpi import candidate_score, select_candidates, to_infrastructure_node


class V012WeeklyBetaTests(unittest.TestCase):
    def test_public_beta_workflow_is_hourly_and_uses_public_profile(self):
        text=Path('.github/workflows/public-beta-monitor.yml').read_text(encoding='utf-8')
        self.assertIn('cron: "17 * * * *"',text)
        self.assertIn('config/sources.public-beta.json',text)
        config=json.loads(Path('config/sources.public-beta.json').read_text(encoding='utf-8'))
        enabled={row['kind'] for row in config['sources'] if row.get('enabled')}
        self.assertEqual({'gdelt','gdacs'},enabled)

    def test_source_coverage_dashboard_uses_collected_data_only(self):
        event=Event(event_id='e1',source_id='gdelt_conflict_news',source_kind='news',title='Conflict report',event_type='media_report',reference_at='2026-08-24T10:00:00+00:00',collected_at='2026-08-24T10:01:00+00:00',verification_level='osint_signal',country='Ukraine')
        with tempfile.TemporaryDirectory() as tmp:
            store=SQLiteStore(Path(tmp)/'beta.db')
            store.upsert_events([event])
            store.record_run(run_id='r1',source_id='gdelt_conflict_news',started_at='2026-08-24T10:00:00+00:00',finished_at='2026-08-24T10:02:00+00:00',status='ok',records=1)
            dashboard=build_source_coverage_dashboard(store)
            store.close()
        self.assertTrue(dashboard['bounded_view'])
        self.assertTrue(dashboard['coverage_not_provider_archive_claim'])
        self.assertEqual(1,dashboard['sources'][0]['events_in_bounded_sample'])

    def test_ucdp_zip_and_case_aggregation(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as archive:
            archive.writestr('data.csv','conflict_id,year,location,side_a,side_b,region,type_of_conflict\n1,2020,State A,Gov,Rebels,1,3\n1,2021,State A,Gov,Rebels,1,3\n2,2021,State A,Gov,Other,1,3\n')
        rows=read_zip_csv(buf.getvalue())
        cases=aggregate_armed_conflict_cases(rows)
        labels=derive_conflict_identity_labels(rows,max_positive=10,max_negative=10)
        self.assertEqual(2,len(cases))
        self.assertGreaterEqual(label_summary(labels)['positive'],1)
        self.assertGreaterEqual(label_summary(labels)['negative'],1)

    def test_historical_base_rate_forecast_is_no_lookahead_benchmark(self):
        cases=[]
        for year in range(2000,2012):
            cases.append({'case_id':f'c{year}','start':f'{year}-01-01','end':f'{year}-12-31','region':'X','outcome_tags':['ceasefire'] if year%2==0 else []})
        forecasts=build_base_rate_forecasts(cases,min_prior_cases=4)
        self.assertTrue(forecasts)
        self.assertTrue(all(row['information_cutoff']<=row['created_at']<row['resolved_at'] for row in forecasts))
        self.assertTrue(all(row['not_a_record_of_live_historical_forecast'] for row in forecasts))
        self.assertIsNotNone(baseline_summary(forecasts)['brier_score'])

    def test_alert_evaluation_metrics(self):
        rows=[
            {'policy_id':'p1','region':'A','predicted':True,'actual':True},
            {'policy_id':'p1','region':'A','predicted':True,'actual':False},
            {'policy_id':'p1','region':'B','predicted':False,'actual':True},
            {'policy_id':'p1','region':'B','predicted':False,'actual':False},
        ]
        metrics=classification_metrics(rows)
        self.assertEqual((1,1,1,1),(metrics['tp'],metrics['fp'],metrics['tn'],metrics['fn']))
        self.assertEqual(0.5,metrics['precision'])
        self.assertIn('p1',evaluate_alert_labels(rows)['by_policy'])

    def test_wpi_candidate_is_structural_not_live_status(self):
        row={'World Port Index Number':'12345','Main Port Name':'Example Port','Country Code':'XX','Latitude':'1.2','Longitude':'3.4','Harbor Size':'Large','Facilities - Container':'Yes','Facilities - Oil Terminal':'Yes','World Water Body':'Test Sea','NAVAREA':'III'}
        node=to_infrastructure_node(row)
        self.assertIsNotNone(node)
        self.assertGreater(candidate_score(row),5)
        self.assertTrue(node['structural_context_not_live_status'])
        selected=select_candidates([row],limit=300)
        self.assertEqual('WPI_12345',selected[0]['node_id'])

    def test_world_bank_latest_observation_preserves_reference_year(self):
        rows=[
            {'country_id':'BRA','indicator_id':'GDP','reference_year':2024,'value':1},
            {'country_id':'BRA','indicator_id':'GDP','reference_year':2025,'value':2},
        ]
        latest=latest_by_country(rows)
        self.assertEqual(2025,latest[0]['reference_year'])
        self.assertEqual(2,latest[0]['value'])

    def test_chokepoint_pack_has_uncertainty_and_not_probability(self):
        pack=build_scenario_pack(scenario_id='s1',route_shares={'Hormuz':0.7,'Other':0.3},disrupted_nodes=['Hormuz'],alternatives={'Hormuz':['Cape']},route_share_uncertainty=0.1,alternative_absorption={'Hormuz':0.25},additional_distance_pct={'Hormuz':40})
        self.assertEqual(0.7,pack['affected_route_share'])
        self.assertLess(pack['affected_route_share_band']['low'],pack['affected_route_share_band']['high'])
        self.assertTrue(pack['structural_exposure_not_event_probability'])

    def test_sanctions_graph_uses_exact_matching_and_keeps_legal_semantics(self):
        index=build_entity_name_index(countries=[{'country_id':'IRN','name':'Iran'}],actors=[{'actor_id':'A1','name':'Example Group'}])
        result=link_designations([{'designation_id':'d1','authority':'X','list_name':'L','effective_date':'2026-01-01','source_url':'https://example','name':'Example Group'}],entity_name_index=index)
        self.assertEqual('A1',result['linked'][0]['entity_id'])
        self.assertTrue(result['linked'][0]['jurisdiction_semantics_required'])
        self.assertTrue(result['fuzzy_matching_requires_review'])

    def test_public_refresh_workflows_are_read_only(self):
        for path in ('.github/workflows/ucdp-bulk-refresh.yml','.github/workflows/wpi-refresh.yml','.github/workflows/worldbank-refresh.yml','.github/workflows/sanctions-refresh.yml'):
            text=Path(path).read_text(encoding='utf-8')
            self.assertIn('contents: read',text,path)
            self.assertIn('upload-artifact@v4',text,path)


if __name__=='__main__':
    unittest.main()

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from geowatch.beta_digest import build_beta_digest, render_beta_digest_markdown
from geowatch.convergence import converge_events
from geowatch.empirical_history import EmpiricalHistory
from geowatch.historical_forecast_baseline import baseline_summary, build_base_rate_forecasts
from geowatch.http import get
from geowatch.models import Event


class _DummyResponse:
    def __init__(self, payload: bytes = b'{}') -> None:
        self._payload = payload
        self.headers = {'Content-Type': 'application/json'}

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def read(self) -> bytes: return self._payload
    def geturl(self) -> str: return 'https://example.test/data'


class V012BetaReliabilityTests(unittest.TestCase):
    def test_public_beta_workflow_has_strict_health_and_persistence(self):
        text = Path('.github/workflows/public-beta-monitor.yml').read_text(encoding='utf-8')
        self.assertIn('concurrency:', text)
        self.assertIn('actions/cache/restore@', text)
        self.assertIn('actions/cache/save@', text)
        self.assertNotIn('actions/cache/restore@v4', text)
        self.assertNotIn('actions/cache/save@v4', text)
        self.assertIn('geowatch-public-beta-v3-', text)
        self.assertIn('state/beta/', text)
        self.assertIn('set -o pipefail', text)
        self.assertIn('scripts/assert_beta_run.py', text)
        self.assertIn('scripts/build_beta_summary.py', text)
        self.assertIn('data/raw/', text)

    def test_live_beta_integration_uses_real_public_profile(self):
        text = Path('.github/workflows/public-beta-integration.yml').read_text(encoding='utf-8')
        self.assertIn('config/sources.public-beta.json', text)
        self.assertIn('scripts/assert_beta_run.py', text)
        self.assertIn('scripts/build_beta_digest.py', text)
        self.assertIn('set -o pipefail', text)

    def test_scheduled_public_refreshes_fail_closed(self):
        for path in ('.github/workflows/ucdp-bulk-refresh.yml','.github/workflows/wpi-refresh.yml','.github/workflows/worldbank-refresh.yml','.github/workflows/sanctions-refresh.yml'):
            text = Path(path).read_text(encoding='utf-8')
            self.assertIn('set -o pipefail', text, path)
            self.assertIn('PYTHONPATH: .', text, path)

    def test_http_get_retries_retryable_status(self):
        error = HTTPError('https://example.test', 429, 'Too Many Requests', {'Retry-After': '0'}, None)
        with patch('geowatch.http.urlopen', side_effect=[error, _DummyResponse()]) as mocked, patch('geowatch.http.time.sleep') as sleeper:
            response = get('https://example.test', retries=1, backoff_seconds=0)
        self.assertEqual(b'{}', response.payload)
        self.assertEqual(2, mocked.call_count)
        sleeper.assert_called_once()

    def test_beta_health_distinguishes_transient_and_structural_failures(self):
        text = Path('scripts/assert_beta_run.py').read_text(encoding='utf-8')
        self.assertIn('transient_source_errors', text)
        self.assertIn('structural_source_errors', text)
        self.assertIn('HTTP Error 429', text)
        self.assertIn('parser_schema_and_configuration_errors_fail_the_beta_run', text)

    def test_context_only_gdacs_cannot_seed_conflict_episode(self):
        event = Event(event_id='gdacs1', source_id='gdacs_context', source_kind='institutional', title='Flood affecting transport corridor', event_type='gdacs_fl', reference_at='2026-08-24T10:00:00+00:00', collected_at='2026-08-24T10:01:00+00:00', verification_level='curated_report', country='Brazil', latitude=-3.1, longitude=-60.0, publisher='gdacs.org')
        episodes, claims, evidence, _, changes = converge_events([event], now=datetime(2026, 8, 24, 12, tzinfo=timezone.utc))
        self.assertEqual([], episodes); self.assertEqual([], claims); self.assertEqual([], evidence); self.assertEqual([], changes)

    def test_sensor_signal_cannot_seed_conflict_episode(self):
        event = Event(event_id='firms1', source_id='nasa_firms_context', source_kind='sensor', title='Thermal anomaly at 1,2', event_type='thermal_anomaly', reference_at='2026-08-24T10:00:00+00:00', collected_at='2026-08-24T10:01:00+00:00', verification_level='sensor_signal', latitude=1.0, longitude=2.0, publisher='NASA FIRMS')
        episodes, claims, evidence, _, _ = converge_events([event], now=datetime(2026, 8, 24, 12, tzinfo=timezone.utc))
        self.assertEqual([], episodes); self.assertEqual([], claims); self.assertEqual([], evidence)

    def test_conflict_news_still_seeds_episode(self):
        event = Event(event_id='news1', source_id='gdelt_conflict_news', source_kind='news', title='Missile strike reported near port', event_type='media_report', reference_at='2026-08-24T10:00:00+00:00', collected_at='2026-08-24T10:01:00+00:00', verification_level='osint_signal', country='Ukraine', publisher='example.com')
        episodes, claims, evidence, _, _ = converge_events([event], now=datetime(2026, 8, 24, 12, tzinfo=timezone.utc))
        self.assertEqual(1, len(episodes)); self.assertEqual(1, len(claims)); self.assertEqual(1, len(evidence))

    def test_empirical_history_preserves_layers_and_hides_future_outcomes(self):
        curated = [{'case_id':'curated-1','start':'2001-01-01','end':'2001-12-31','region':'A','outcome_tags':['ceasefire'],'source_ids':['s1']}]
        ucdp = [{'case_id':'ucdp-1','start':'2002-01-01','end':'2004-12-31','region':'B','outcome_tags':['peace_agreement'],'source_ids':['ucdp']}]
        history = EmpiricalHistory(curated, ucdp)
        layered = history.layered_cases()
        self.assertEqual({'project_curated','ucdp_research_coded'}, {row['corpus_layer'] for row in layered})
        self.assertFalse(next(row for row in layered if row['case_id']=='ucdp-1')['human_gold'])
        active = next(row for row in history.as_of('2003-01-01') if row['case_id']=='ucdp-1')
        self.assertEqual([], active['outcome_tags']); self.assertTrue(active['outcome_hidden_due_to_cutoff'])

    def test_ucdp_baseline_only_scores_supported_outcomes(self):
        cases=[]
        for year in range(2000, 2015):
            cases.append({'case_id':f'c{year}','start':f'{year}-01-01','end':f'{year}-12-31','outcome_tags':['ceasefire'] if year%2==0 else ['peace_agreement']})
        rows = build_base_rate_forecasts(cases, outcome_tags=('ceasefire','peace_agreement'), min_prior_cases=4)
        summary = baseline_summary(rows)
        self.assertEqual({'ceasefire','peace_agreement'}, set(summary['by_outcome']))
        self.assertNotIn('territorial_change', summary['by_outcome'])

    def test_beta_digest_preserves_non_probability_semantics(self):
        episode_report = {'generated_at':'2026-08-24T20:00:00+00:00','episode_count':1,'episodes':[{'episode_id':'ep1','title':'Example episode','state':'active','countries':['A'],'last_updated_at':'2026-08-24T19:00:00+00:00','evidence_strength':{'overall_index':72},'change_flags':['new_claim'],'claims':[{'claim_id':'c1'}],'evidence':[{'evidence_id':'e1'}],'recent_events':[{'source_id':'gdelt_conflict_news','publisher':'Example News'}]}]}
        coverage = {'sources':[{'source_id':'gdelt_conflict_news','last_run_status':'ok','last_run_records':4,'last_reference_in_bounded_sample':'2026-08-24T19:00:00+00:00'}]}
        digest = build_beta_digest(episode_report, coverage)
        self.assertTrue(digest['source_health']['all_last_runs_ok'])
        self.assertTrue(digest['top_episodes'][0]['evidence_strength_not_probability'])
        markdown = render_beta_digest_markdown(digest)
        self.assertIn('not probability', markdown); self.assertIn('Example episode', markdown)

    def test_empirical_builder_is_explicitly_not_human_gold(self):
        text = Path('scripts/build_empirical_history_artifacts.py').read_text(encoding='utf-8')
        self.assertIn('human_gold_requires_explicit_review', text)
        self.assertIn('research_coded_history_is_not_live_event_evidence', text)


if __name__ == '__main__': unittest.main()

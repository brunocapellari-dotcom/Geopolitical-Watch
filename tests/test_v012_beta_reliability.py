from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from geowatch.empirical_history import EmpiricalHistory
from geowatch.historical_forecast_baseline import baseline_summary, build_base_rate_forecasts


class V012BetaReliabilityTests(unittest.TestCase):
    def test_public_beta_workflow_has_strict_health_and_persistence(self):
        text = Path('.github/workflows/public-beta-monitor.yml').read_text(encoding='utf-8')
        self.assertIn('concurrency:', text)
        self.assertIn('actions/cache/restore@v4', text)
        self.assertIn('actions/cache/save@v4', text)
        self.assertIn('set -o pipefail', text)
        self.assertIn('scripts/assert_beta_run.py', text)
        self.assertIn('data/raw/', text)

    def test_live_beta_integration_uses_real_public_profile(self):
        text = Path('.github/workflows/public-beta-integration.yml').read_text(encoding='utf-8')
        self.assertIn('config/sources.public-beta.json', text)
        self.assertIn('scripts/assert_beta_run.py', text)
        self.assertIn('set -o pipefail', text)

    def test_scheduled_public_refreshes_fail_closed(self):
        for path in (
            '.github/workflows/ucdp-bulk-refresh.yml',
            '.github/workflows/wpi-refresh.yml',
            '.github/workflows/worldbank-refresh.yml',
            '.github/workflows/sanctions-refresh.yml',
        ):
            text = Path(path).read_text(encoding='utf-8')
            self.assertIn('set -o pipefail', text, path)
            self.assertIn('PYTHONPATH: .', text, path)

    def test_empirical_history_preserves_layers_and_hides_future_outcomes(self):
        curated = [{
            'case_id': 'curated-1', 'start': '2001-01-01', 'end': '2001-12-31',
            'region': 'A', 'outcome_tags': ['ceasefire'], 'source_ids': ['s1']
        }]
        ucdp = [{
            'case_id': 'ucdp-1', 'start': '2002-01-01', 'end': '2004-12-31',
            'region': 'B', 'outcome_tags': ['peace_agreement'], 'source_ids': ['ucdp']
        }]
        history = EmpiricalHistory(curated, ucdp)
        layered = history.layered_cases()
        self.assertEqual({'project_curated', 'ucdp_research_coded'}, {row['corpus_layer'] for row in layered})
        self.assertFalse(next(row for row in layered if row['case_id'] == 'ucdp-1')['human_gold'])
        as_of = history.as_of('2003-01-01')
        active = next(row for row in as_of if row['case_id'] == 'ucdp-1')
        self.assertEqual([], active['outcome_tags'])
        self.assertTrue(active['outcome_hidden_due_to_cutoff'])

    def test_ucdp_baseline_only_scores_supported_outcomes(self):
        cases = []
        for year in range(2000, 2015):
            cases.append({
                'case_id': f'c{year}',
                'start': f'{year}-01-01',
                'end': f'{year}-12-31',
                'outcome_tags': ['ceasefire'] if year % 2 == 0 else ['peace_agreement'],
            })
        rows = build_base_rate_forecasts(cases, outcome_tags=('ceasefire', 'peace_agreement'), min_prior_cases=4)
        summary = baseline_summary(rows)
        self.assertEqual({'ceasefire', 'peace_agreement'}, set(summary['by_outcome']))
        self.assertNotIn('territorial_change', summary['by_outcome'])

    def test_empirical_builder_is_explicitly_not_human_gold(self):
        text = Path('scripts/build_empirical_history_artifacts.py').read_text(encoding='utf-8')
        self.assertIn('human_gold_requires_explicit_review', text)
        self.assertIn('research_coded_history_is_not_live_event_evidence', text)


if __name__ == '__main__':
    unittest.main()

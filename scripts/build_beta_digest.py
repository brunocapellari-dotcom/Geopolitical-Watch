from __future__ import annotations

import json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.beta_digest import build_beta_digest, render_beta_digest_markdown


def main() -> int:
    episode_report = json.loads(Path('reports/episodes/latest.json').read_text(encoding='utf-8'))
    coverage = json.loads(Path('reports/beta_coverage.json').read_text(encoding='utf-8'))
    health_path = Path('reports/beta_health.json')
    run_health = json.loads(health_path.read_text(encoding='utf-8')) if health_path.exists() else {}
    digest = build_beta_digest(episode_report, coverage, run_health=run_health, max_episodes=12)
    Path('reports/beta_digest.json').write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding='utf-8')
    Path('reports/beta_digest.md').write_text(render_beta_digest_markdown(digest), encoding='utf-8')
    print(json.dumps({
        'schema_version':'geowatch-public-beta-digest-build-v2',
        'episodes_in_digest':digest['episodes_in_digest'],
        'all_last_runs_ok':digest['source_health']['all_last_runs_ok'],
        'degraded':digest['operational_status']['degraded'],
        'conflict_coverage_available':digest['operational_status']['conflict_coverage_available'],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

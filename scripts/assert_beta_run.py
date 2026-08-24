from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="beta-run.json")
    parser.add_argument("--db", default="data/beta.db")
    parser.add_argument("--reports", default="reports")
    args = parser.parse_args()

    run_path = Path(args.run)
    db_path = Path(args.db)
    reports_root = Path(args.reports)
    checks: list[dict] = []

    if not run_path.exists():
        checks.append({"check": "run_summary_exists", "passed": False, "detail": str(run_path)})
        payload = {}
    else:
        payload = _load(run_path)
        checks.append({"check": "run_summary_exists", "passed": True, "detail": str(run_path)})

    source_results = payload.get("source_results") or []
    checks.append({
        "check": "sources_attempted",
        "passed": len(source_results) >= 2,
        "detail": f"sources={len(source_results)}",
    })
    errors = [row for row in source_results if row.get("status") != "ok"]
    checks.append({
        "check": "all_enabled_sources_ok",
        "passed": not errors,
        "detail": "; ".join(f"{row.get('source_id')}={row.get('error') or row.get('status')}" for row in errors) or "ok",
    })

    checks.append({
        "check": "database_persisted",
        "passed": db_path.exists() and db_path.stat().st_size > 0,
        "detail": f"exists={db_path.exists()} size={db_path.stat().st_size if db_path.exists() else 0}",
    })

    situational = reports_root / "latest.json"
    episodes = reports_root / "episodes" / "latest.json"
    checks.append({
        "check": "situational_report_generated",
        "passed": situational.exists(),
        "detail": str(situational),
    })
    checks.append({
        "check": "episode_report_generated",
        "passed": episodes.exists(),
        "detail": str(episodes),
    })

    for key in ("analysis_events", "clusters", "episodes", "episode_changes", "alerts_generated", "alerts_enqueued"):
        value = payload.get(key)
        checks.append({
            "check": f"numeric_{key}",
            "passed": isinstance(value, int) and value >= 0,
            "detail": f"{key}={value!r}",
        })

    passed = all(row["passed"] for row in checks)
    output = {
        "schema_version": "geowatch-public-beta-health-v1",
        "passed": passed,
        "checks": checks,
        "zero_events_is_allowed_if_sources_succeeded": True,
        "source_http_or_parser_errors_fail_the_beta_run": True,
        "beta_health_does_not_close_v1_production_hard_gates": True,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path


_TRANSIENT_MARKERS = (
    "HTTP Error 429",
    "HTTP Error 500",
    "HTTP Error 502",
    "HTTP Error 503",
    "HTTP Error 504",
    "timed out",
    "TimeoutError",
    "Temporary failure",
    "Connection reset",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_transient(row: dict) -> bool:
    error = str(row.get("error") or "")
    return any(marker.casefold() in error.casefold() for marker in _TRANSIENT_MARKERS)


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
    successful = [row for row in source_results if row.get("status") == "ok"]
    errors = [row for row in source_results if row.get("status") != "ok"]
    transient = [row for row in errors if _is_transient(row)]
    structural = [row for row in errors if not _is_transient(row)]

    checks.append({
        "check": "minimum_operational_source_succeeded",
        "passed": bool(successful),
        "detail": f"successful={len(successful)} attempted={len(source_results)}",
    })
    checks.append({
        "check": "no_structural_source_errors",
        "passed": not structural,
        "detail": "; ".join(f"{row.get('source_id')}={row.get('error') or row.get('status')}" for row in structural) or "ok",
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
        "schema_version": "geowatch-public-beta-health-v2",
        "passed": passed,
        "degraded": bool(transient),
        "successful_sources": [row.get("source_id") for row in successful],
        "transient_source_errors": [
            {"source_id": row.get("source_id"), "error": row.get("error")} for row in transient
        ],
        "structural_source_errors": [
            {"source_id": row.get("source_id"), "error": row.get("error")} for row in structural
        ],
        "checks": checks,
        "zero_events_is_allowed_if_at_least_one_source_succeeded": True,
        "transient_rate_limit_or_5xx_can_degrade_without_faking_source_success": True,
        "parser_schema_and_configuration_errors_fail_the_beta_run": True,
        "failed_source_checkpoint_is_not_advanced_by_pipeline": True,
        "beta_health_does_not_close_v1_production_hard_gates": True,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

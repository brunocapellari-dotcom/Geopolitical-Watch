from __future__ import annotations

import json
from pathlib import Path

from geowatch.historical_forecast_baseline import baseline_summary, build_base_rate_forecasts
from geowatch.ucdp_bulk import (
    aggregate_actor_profiles,
    aggregate_armed_conflict_cases,
    download_rows,
    enrich_cases_with_termination,
    termination_outcomes,
)


def main() -> int:
    out = Path("generated/ucdp")
    out.mkdir(parents=True, exist_ok=True)

    acd_rows, acd_url = download_rows("armed_conflict_26_1")
    cases = aggregate_armed_conflict_cases(acd_rows)

    termination_rows, termination_url = download_rows("termination_4_2024")
    cases = enrich_cases_with_termination(cases, termination_outcomes(termination_rows))

    actor_rows, actor_url = download_rows("actor_26_1")
    actors = aggregate_actor_profiles(actor_rows)

    forecasts = build_base_rate_forecasts(cases)
    summary = {
        "schema_version": "geowatch-ucdp-bulk-build-v1",
        "case_count": len(cases),
        "actor_count": len(actors),
        "baseline_forecast_count": len(forecasts),
        "baseline": baseline_summary(forecasts),
        "sources": {
            "armed_conflict": acd_url,
            "termination": termination_url,
            "actors": actor_url,
        },
        "license": "UCDP datasets are distributed under CC BY 4.0; preserve citations/version metadata.",
    }

    (out / "historical_cases.json").write_text(json.dumps({"schema_version":"geowatch-ucdp-historical-cases-v1","cases":cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "actors.json").write_text(json.dumps({"schema_version":"geowatch-ucdp-actors-v1","profiles":actors}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "baseline_forecasts.json").write_text(json.dumps({"schema_version":"geowatch-historical-baseline-v1","forecasts":forecasts}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

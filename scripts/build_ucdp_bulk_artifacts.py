from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from geowatch.historical_forecast_baseline import baseline_summary, build_base_rate_forecasts
from geowatch.ucdp_bulk import (
    aggregate_actor_profiles,
    aggregate_armed_conflict_cases,
    download_rows,
    enrich_cases_with_termination,
    termination_outcomes,
)
from geowatch.ucdp_labels import derive_conflict_identity_labels, label_summary


def main() -> int:
    out = Path("generated/ucdp")
    out.mkdir(parents=True, exist_ok=True)

    acd_rows, acd_url = download_rows("armed_conflict_26_1")
    cases = aggregate_armed_conflict_cases(acd_rows)
    labels = derive_conflict_identity_labels(acd_rows)

    termination_rows, termination_url = download_rows("termination_4_2024")
    terminations = termination_outcomes(termination_rows)
    cases = enrich_cases_with_termination(cases, terminations)

    actor_rows, actor_url = download_rows("actor_26_1")
    actors = aggregate_actor_profiles(actor_rows)

    forecasts = build_base_rate_forecasts(cases)
    outcome_counts = Counter(tag for case in cases for tag in case.get("outcome_tags", []))
    current_like = [case for case in cases if case.get("active_at_dataset_end")]
    matched_terminations = sum(1 for case in cases if "ucdp_termination_4_2024" in set(case.get("source_ids", [])))
    years = [year for case in cases for year in case.get("active_years", [])]
    summary = {
        "schema_version": "geowatch-ucdp-bulk-build-v2",
        "dataset_versions": {
            "armed_conflict": "26.1",
            "actor": "26.1",
            "termination": "4-2024",
        },
        "raw_rows": {
            "armed_conflict_year_rows": len(acd_rows),
            "actor_rows": len(actor_rows),
            "termination_rows": len(termination_rows),
        },
        "continuous_episode_count": len(cases),
        "distinct_conflict_id_count": len({case.get("ucdp_conflict_id") for case in cases}),
        "actor_count": len(actors),
        "active_at_dataset_end_count": len(current_like),
        "termination_matches": matched_terminations,
        "termination_unmatched_episode_count": len(cases) - matched_terminations,
        "outcome_tag_counts": dict(sorted(outcome_counts.items())),
        "historical_year_min": min(years) if years else None,
        "historical_year_max": max(years) if years else None,
        "identity_labels": label_summary(labels),
        "baseline_forecast_count": len(forecasts),
        "baseline": baseline_summary(forecasts),
        "sources": {
            "armed_conflict": acd_url,
            "termination": termination_url,
            "actors": actor_url,
        },
        "governance": {
            "license": "UCDP bulk datasets are CC BY 4.0; preserve citations/version metadata.",
            "continuous_episode_split": True,
            "missing_termination_record_is_not_an_outcome": True,
            "active_at_dataset_end_is_dataset_state_not_live_confirmation": True,
            "identity_labels_are_not_human_gold": True,
            "baseline_forecasts_are_retroactive_benchmarks_not_historical_live_predictions": True,
        },
    }

    (out / "historical_cases.json").write_text(
        json.dumps({"schema_version":"geowatch-ucdp-historical-cases-v2","cases":cases}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "actors.json").write_text(
        json.dumps({"schema_version":"geowatch-ucdp-actors-v2","profiles":actors}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "identity_labels.json").write_text(
        json.dumps({"schema_version":"geowatch-ucdp-identity-labels-v1","labels":labels,"human_gold":False}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "baseline_forecasts.json").write_text(
        json.dumps({"schema_version":"geowatch-historical-baseline-v1","forecasts":forecasts}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

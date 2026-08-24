from __future__ import annotations

import json
from pathlib import Path


def _read(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _check(name: str, condition: bool, detail: str) -> dict:
    return {"check": name, "passed": bool(condition), "detail": detail}


def main() -> int:
    ucdp = _read("generated/ucdp/summary.json")
    empirical = _read("generated/empirical/summary.json")
    wpi = _read("generated/wpi/summary.json")
    worldbank = _read("generated/worldbank/summary.json")
    sanctions = _read("generated/sanctions/summary.json")
    unique_sanctions = sanctions.get("unique_designation_id_counts") or sanctions.get("counts", {})
    supported = set(ucdp.get("forecast_supported_outcomes") or [])
    observed = set((ucdp.get("outcome_tag_counts") or {}).keys())

    checks = [
        _check("ucdp_conflict_rows", int(ucdp.get("raw_rows", {}).get("armed_conflict_year_rows", 0)) >= 500,
               f"rows={ucdp.get('raw_rows', {}).get('armed_conflict_year_rows')}"),
        _check("ucdp_continuous_episodes", int(ucdp.get("continuous_episode_count", 0)) >= 100,
               f"episodes={ucdp.get('continuous_episode_count')}"),
        _check("ucdp_actors", int(ucdp.get("actor_count", 0)) >= 500,
               f"actors={ucdp.get('actor_count')}"),
        _check("ucdp_identity_labels", int(ucdp.get("identity_labels", {}).get("label_count", 0)) >= 100,
               f"labels={ucdp.get('identity_labels', {}).get('label_count')}"),
        _check("ucdp_history_range", int(ucdp.get("historical_year_min") or 9999) <= 1950 and int(ucdp.get("historical_year_max") or 0) >= 2025,
               f"range={ucdp.get('historical_year_min')}..{ucdp.get('historical_year_max')}"),
        _check("ucdp_forecast_labels_supported", bool(supported) and supported == observed,
               f"supported={sorted(supported)} observed={sorted(observed)}"),
        _check("empirical_history_total", int(empirical.get("total_case_count", 0)) >= 650,
               f"cases={empirical.get('total_case_count')}"),
        _check("empirical_ucdp_layer", int(empirical.get("ucdp_research_coded_count", 0)) >= 100,
               f"ucdp_cases={empirical.get('ucdp_research_coded_count')}"),
        _check("empirical_layers_distinct", bool(empirical.get("layers_remain_distinct")),
               f"layers_remain_distinct={empirical.get('layers_remain_distinct')}"),
        _check("wpi_source_rows", int(wpi.get("source_row_count", 0)) >= 1000,
               f"rows={wpi.get('source_row_count')}"),
        _check("wpi_candidates", int(wpi.get("candidate_count", 0)) >= 250,
               f"candidates={wpi.get('candidate_count')}"),
        _check("worldbank_countries", int(worldbank.get("country_count", 0)) >= 180,
               f"countries={worldbank.get('country_count')}"),
        _check("worldbank_indicators", int(worldbank.get("indicator_count", 0)) >= 5,
               f"indicators={worldbank.get('indicator_count')}"),
        _check("worldbank_observations", int(worldbank.get("observation_count", 0)) >= 1000,
               f"observations={worldbank.get('observation_count')}"),
        _check("unsc_unique_designations", int(unique_sanctions.get("unsc", 0)) >= 10,
               f"unique_ids={unique_sanctions.get('unsc')}"),
        _check("uk_unique_designations", int(unique_sanctions.get("uk", 0)) >= 1000,
               f"unique_ids={unique_sanctions.get('uk')}"),
    ]
    passed = all(row["passed"] for row in checks)
    output = {
        "schema_version": "geowatch-public-bootstrap-smoke-v3",
        "passed": passed,
        "checks": checks,
        "thresholds_are_sanity_checks_not_completeness_claims": True,
        "sanctions_thresholds_use_unique_provider_ids_not_flattened_csv_rows": True,
        "forecast_scoring_uses_only_observed_supported_outcome_labels": True,
        "empirical_history_keeps_project_and_research_coded_layers_distinct": True,
        "public_bootstrap_pass_does_not_close_v1_hard_gates": True,
    }
    out = Path("generated/public-bootstrap-smoke.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

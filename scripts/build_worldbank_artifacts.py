from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from _repo_path import ensure_repo_path

ensure_repo_path()

from geowatch.worldbank import countries, indicator, latest_by_country, load_registry


def main() -> int:
    registry = load_registry()
    current_year = datetime.now(timezone.utc).year
    start_year = current_year - 5
    country_rows, country_url = countries()
    observations = []
    urls = {}
    for spec in registry.get("indicators", []):
        rows, url = indicator(spec["id"], start_year=start_year, end_year=current_year)
        observations.extend(rows)
        urls[spec["id"]] = url
    latest = latest_by_country(observations)
    out = Path("generated/worldbank")
    out.mkdir(parents=True, exist_ok=True)
    (out / "countries.json").write_text(json.dumps({"schema_version":"geowatch-worldbank-countries-v1","countries":country_rows,"source_url":country_url}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "observations.json").write_text(json.dumps({"schema_version":"geowatch-worldbank-observations-v1","observations":observations,"source_urls":urls}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "latest_observations.json").write_text(json.dumps({"schema_version":"geowatch-worldbank-latest-v1","observations":latest}, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "schema_version":"geowatch-worldbank-build-summary-v1",
        "country_count":len(country_rows),
        "observation_count":len(observations),
        "latest_observation_count":len(latest),
        "indicator_count":len(registry.get("indicators", [])),
        "start_year":start_year,
        "end_year":current_year,
        "economic_context_not_conflict_evidence":True
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.historical_forecast_baseline import baseline_summary, build_base_rate_forecasts
from geowatch.historical_validation_assets import build_chronologies, build_gold_review_candidates, build_frozen_forecast_bank, summarize_forecast_bank
from geowatch.human_gold import make_review_batch
from geowatch.ucdp_bulk import aggregate_actor_profiles, aggregate_armed_conflict_cases, download_rows, enrich_cases_with_termination, termination_outcomes
from geowatch.ucdp_labels import derive_conflict_identity_labels, label_summary


def main() -> int:
    out=Path("generated/ucdp"); out.mkdir(parents=True,exist_ok=True)
    acd_rows,acd_url=download_rows("armed_conflict_26_1")
    cases=aggregate_armed_conflict_cases(acd_rows); labels=derive_conflict_identity_labels(acd_rows)
    termination_rows,termination_url=download_rows("termination_4_2024")
    cases=enrich_cases_with_termination(cases,termination_outcomes(termination_rows))
    actor_rows,actor_url=download_rows("actor_26_1"); actors=aggregate_actor_profiles(actor_rows)
    outcome_counts=Counter(tag for case in cases for tag in case.get("outcome_tags",[])); supported_outcomes=tuple(sorted(outcome_counts))
    forecasts=build_base_rate_forecasts(cases,outcome_tags=supported_outcomes)
    chronologies=build_chronologies(cases,limit=150); gold_candidates=build_gold_review_candidates(cases,limit=500)
    frozen=build_frozen_forecast_bank(cases,limit=240); frozen_summary=summarize_forecast_bank(frozen)
    current_like=[case for case in cases if case.get("active_at_dataset_end")]
    matched=sum(1 for case in cases if "ucdp_termination_4_2024" in set(case.get("source_ids",[])))
    years=[year for case in cases for year in case.get("active_years",[])]
    review_batches=[]
    for index in range(5):
        chunk=gold_candidates[index*100:(index+1)*100]
        review_batches.append(make_review_batch(chunk,batch_id=f"ucdp-gold-{index+1:03d}",limit=100))
    summary={
      "schema_version":"geowatch-ucdp-bulk-build-v5","dataset_versions":{"armed_conflict":"26.1","actor":"26.1","termination":"4-2024"},
      "raw_rows":{"armed_conflict_year_rows":len(acd_rows),"actor_rows":len(actor_rows),"termination_rows":len(termination_rows)},
      "continuous_episode_count":len(cases),"distinct_conflict_id_count":len({case.get("ucdp_conflict_id") for case in cases}),"actor_count":len(actors),
      "active_at_dataset_end_count":len(current_like),"termination_matches":matched,"termination_unmatched_episode_count":len(cases)-matched,
      "outcome_tag_counts":dict(sorted(outcome_counts.items())),"forecast_supported_outcomes":list(supported_outcomes),
      "historical_year_min":min(years) if years else None,"historical_year_max":max(years) if years else None,
      "identity_labels":label_summary(labels),"baseline_forecast_count":len(forecasts),"baseline":baseline_summary(forecasts),
      "chronology_count":len(chronologies),"gold_review_candidate_count":len(gold_candidates),"human_review_batch_count":len(review_batches),
      "human_review_items_prepared":sum(b["count"] for b in review_batches),"human_gold_completed_count":0,"frozen_forecast_bank":frozen_summary,
      "sources":{"armed_conflict":acd_url,"termination":termination_url,"actors":actor_url},
      "governance":{"license":"UCDP bulk datasets are CC BY 4.0; preserve citations/version metadata.","continuous_episode_split":True,
        "identity_labels_are_not_human_gold":True,"gold_candidates_require_explicit_human_review":True,"chronologies_are_research_coded":True,
        "review_batches_are_not_gold_until_human_label_reviewer_and_timestamp_exist":True,
        "frozen_forecasts_are_retroactive_benchmarks_not_live_historical_predictions":True,"unsupported_outcomes_are_not_scored_as_negatives":True}
    }
    files={
      "historical_cases.json":{"schema_version":"geowatch-ucdp-historical-cases-v2","cases":cases},
      "actors.json":{"schema_version":"geowatch-ucdp-actors-v2","profiles":actors},
      "identity_labels.json":{"schema_version":"geowatch-ucdp-identity-labels-v1","labels":labels,"human_gold":False},
      "baseline_forecasts.json":{"schema_version":"geowatch-historical-baseline-v2","supported_outcomes":list(supported_outcomes),"forecasts":forecasts},
      "chronologies.json":{"schema_version":"geowatch-ucdp-chronologies-v1","chronologies":chronologies,"research_coded":True},
      "gold_review_candidates.json":{"schema_version":"geowatch-gold-review-candidates-v1","candidates":gold_candidates,"human_gold":False},
      "frozen_forecast_bank.json":{"schema_version":"geowatch-frozen-forecast-bank-v1","summary":frozen_summary,"forecasts":frozen},
      "summary.json":summary,
    }
    for idx,batch in enumerate(review_batches,1): files[f"human_review_batch_{idx:03d}.json"]=batch
    for name,payload in files.items(): (out/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.actor_profiles import ActorProfiles
from geowatch.infrastructure_review import review_wpi_candidates
from geowatch.profile_enrichment import ProfileEnrichmentQueue
from geowatch.readiness import current_code_readiness_estimate
from geowatch.release_audit import ReleaseAudit
from geowatch.rolling_validation import rolling_oos_report
from geowatch.scenario_catalog import ScenarioCatalog


def _load(path:str)->dict: return json.loads(Path(path).read_text(encoding="utf-8"))


def _forecast_rows(rows:list[dict])->list[dict]:
    return [{"forecast_id":r["forecast_id"],"probability":float(r["baseline_probability"]),"outcome":int(bool(r["observed_outcome"])),"created_at":r["created_at"],"information_cutoff":r["information_cutoff"],"resolved_at":r["resolved_at"],"horizon_days":r["horizon_days"],"region":r.get("region") or "unknown","source_mix":r.get("source_mix") or ["unknown"]} for r in rows]


def _forecast_metrics(rows:list[dict])->dict:
    groups=defaultdict(list)
    for row in rows: groups[int(row["horizon_days"])].append(row)
    by_h={}
    for h,vals in sorted(groups.items()):
        b=sum((float(v["baseline_probability"])-int(bool(v["observed_outcome"])))**2 for v in vals)/len(vals)
        by_h[str(h)]={"count":len(vals),"brier_score":round(b,6)}
    return {"count":len(rows),"by_horizon":by_h,"retrospective_benchmark_not_prospective_track_record":True}


def main()->int:
    ucdp=_load("generated/ucdp/summary.json"); frozen=_load("generated/ucdp/frozen_forecast_bank.json")
    wpi=_load("generated/wpi/critical_port_candidates.json"); infra=review_wpi_candidates(list(wpi.get("nodes") or []))
    profiles=ProfileEnrichmentQueue.from_files().progress(); actors=ActorProfiles.from_json().coverage(); scenarios=ScenarioCatalog.from_json().summary()
    tier2=next((r for r in profiles["tiers"] if int(r["tier"])==2),{"ratio":0})
    raw_forecasts=list(frozen.get("forecasts") or []); forecast_metrics=_forecast_metrics(raw_forecasts)
    oos=rolling_oos_report(forecasts=_forecast_rows(raw_forecasts))
    oos_accepted=int((oos.get("forecast_backtest") or {}).get("accepted") or 0)
    region_slices=len((oos.get("by_region") or {}).get("forecasts") or {})
    source_mix_slices=len((oos.get("by_source_mix") or {}).get("forecasts") or {})
    release=ReleaseAudit.from_files().evaluate(enabled_sources={"gdelt_conflict_news","gdacs_context","ucdp_bulk_26_1","world_bank_wdi","nga_world_port_index","unsc_sanctions","uk_sanctions"},evidence={"production_smoke":False,"restore_drill":False,"historical_oos":False,"security_review":False,"cost_review":False})
    checks=[
      {"id":"tier2_profiles_80pct","passed":float(tier2.get("ratio") or 0)>=0.8,"value":tier2.get("ratio")},
      {"id":"strategic_actors_50","passed":int(actors.get("profile_count") or 0)>=50,"value":actors.get("profile_count")},
      {"id":"ucdp_chronologies_150","passed":int(ucdp.get("chronology_count") or 0)>=150,"value":ucdp.get("chronology_count")},
      {"id":"frozen_forecasts_200","passed":int(forecast_metrics["count"])>=200,"value":forecast_metrics["count"]},
      {"id":"rolling_oos_forecasts_200","passed":oos_accepted>=200,"value":oos_accepted},
      {"id":"rolling_oos_region_slices","passed":region_slices>=2,"value":region_slices},
      {"id":"rolling_oos_source_mix_slices","passed":source_mix_slices>=1,"value":source_mix_slices},
      {"id":"scenario_packs_5","passed":int(scenarios.get("scenario_count") or 0)>=5,"value":scenarios.get("scenario_count")},
      {"id":"wpi_candidates_250","passed":int(infra.get("candidate_count") or 0)>=250,"value":infra.get("candidate_count")},
    ]
    payload={"schema_version":"geowatch-v013-operational-assets-v2","checks":checks,"passed":all(r["passed"] for r in checks),"profile_progress":profiles,"actor_coverage":actors,"forecast_metrics":forecast_metrics,"rolling_oos":oos,"infrastructure_review":{k:v for k,v in infra.items() if k!="nodes"},"scenario_catalog":scenarios,"readiness":current_code_readiness_estimate(),"v1_go_no_go":release,"human_gold":{"completed":int(ucdp.get("human_gold_completed_count") or 0),"candidate_count":int(ucdp.get("gold_review_candidate_count") or 0),"requires_explicit_human_review":True},"limitations":{"rolling_oos_is_research_coded_benchmark_not_completed_human_gold_gate":True,"wpi_reviewed_critical_requires_second_authoritative_source":True,"human_gold_not_synthesized":True,"production_hard_gates_not_inferred_from_code":True}}
    out=Path("generated/v013"); out.mkdir(parents=True,exist_ok=True)
    (out/"rolling_oos.json").write_text(json.dumps(oos,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"v1_go_no_go.json").write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"operational_assets.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0 if payload["passed"] else 1

if __name__=="__main__": raise SystemExit(main())

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Iterable

SUPPORTED_OUTCOMES=("ceasefire","peace_agreement")
FORECAST_HORIZONS=(1,7,30,90)


def build_chronologies(cases: Iterable[dict], *, limit: int = 150) -> list[dict]:
    rows=[]
    for case in cases:
        years=list(case.get("active_years") or [])
        duration=(max(years)-min(years)+1) if years else 0
        score=(2 if case.get("active_at_dataset_end") else 0)+min(duration,20)/20+(1 if case.get("outcome_tags") else 0)
        timeline=[{"date":f"{year}-01-01","event":"active_year","source_id":"ucdp_prio_acd_26_1"} for year in years]
        if case.get("end"):
            timeline.append({"date":case["end"],"event":"episode_end","outcome_tags":list(case.get("outcome_tags") or []),"source_id":"ucdp_termination_4_2024" if "ucdp_termination_4_2024" in case.get("source_ids",[]) else "ucdp_prio_acd_26_1"})
        rows.append({
            "case_id":case.get("case_id"),"ucdp_conflict_id":case.get("ucdp_conflict_id"),"ucdp_episode_no":case.get("ucdp_episode_no"),
            "location":case.get("location"),"region":case.get("region"),"actors":list(case.get("actors") or []),
            "start":case.get("start"),"end":case.get("end"),"active_years":years,"outcome_tags":list(case.get("outcome_tags") or []),
            "source_ids":list(case.get("source_ids") or []),"timeline":sorted(timeline,key=lambda r:r["date"]),
            "priority_score":round(score,3),"research_coded_not_human_gold":True,"historical_context_not_live_evidence":True,
        })
    return sorted(rows,key=lambda r:(r["priority_score"],r.get("end") or "9999",r.get("start") or ""),reverse=True)[:limit]


def build_gold_review_candidates(cases: Iterable[dict], *, limit: int = 500) -> list[dict]:
    by_conflict: dict[str,list[dict]]=defaultdict(list)
    for row in cases: by_conflict[str(row.get("ucdp_conflict_id"))].append(dict(row))
    candidates=[]
    for cid,values in by_conflict.items():
        ordered=sorted(values,key=lambda r:(int(r.get("ucdp_episode_no") or 0),str(r.get("start") or "")))
        for left,right in zip(ordered,ordered[1:]):
            candidates.append({
                "candidate_id":f"gold:merge_split:{left['case_id']}:{right['case_id']}","task_type":"episode_merge_split",
                "left_case_id":left["case_id"],"right_case_id":right["case_id"],"ucdp_conflict_id":cid,
                "machine_context":{"left_end":left.get("end"),"right_start":right.get("start"),"same_ucdp_conflict_id":True},
                "review_status":"unreviewed","human_gold":False,
                "review_question":"Should these research-coded episodes remain separate for Geopolitical Watch convergence evaluation?",
            })
    for row in cases:
        candidates.append({
            "candidate_id":f"gold:conflict_context:{row['case_id']}","task_type":"conflict_vs_context","case_id":row["case_id"],
            "machine_context":{"actors":list(row.get("actors") or []),"types":list(row.get("types") or []),"region":row.get("region")},
            "review_status":"unreviewed","human_gold":False,
            "review_question":"Would this episode qualify as conflict evidence rather than context-only under Geopolitical Watch rules?",
        })
    return candidates[:limit]


def build_frozen_forecast_bank(cases: Iterable[dict], *, limit: int = 240) -> list[dict]:
    rows=sorted((dict(r) for r in cases if r.get("start") and r.get("end")),key=lambda r:r["start"])
    bank=[]
    for case in rows:
        start=_d(case["start"]); end=_d(case["end"])
        prior=[r for r in rows if r.get("end") and _d(r["end"])<start]
        if len(prior)<20: continue
        for tag in SUPPORTED_OUTCOMES:
            prior_with_tag=sum(tag in set(r.get("outcome_tags") or []) for r in prior)
            base=(prior_with_tag+1)/(len(prior)+2)
            for horizon in FORECAST_HORIZONS:
                resolution_deadline=start+timedelta(days=horizon)
                observed=bool(tag in set(case.get("outcome_tags") or []) and end<=resolution_deadline)
                bank.append({
                    "forecast_id":f"frozen:{case['case_id']}:{tag}:{horizon}d","case_id":case["case_id"],"outcome_tag":tag,
                    "horizon_days":horizon,"question":f"Will episode {case['case_id']} resolve with {tag} within {horizon} days of its start?",
                    "created_at":(start-timedelta(days=1)).isoformat(),"information_cutoff":(start-timedelta(days=1)).isoformat(),
                    "resolution_deadline":resolution_deadline.isoformat(),"observed_outcome":observed,"resolved_at":min(end,resolution_deadline).isoformat(),
                    "baseline_probability":round(base,6),"frozen_template":True,"retrospective_benchmark_not_live_historical_forecast":True,
                })
                if len(bank)>=limit: return bank
    return bank


def summarize_forecast_bank(rows: Iterable[dict]) -> dict:
    values=list(rows); by_h=Counter(int(r["horizon_days"]) for r in values); by_tag=Counter(str(r["outcome_tag"]) for r in values)
    brier=sum((float(r["baseline_probability"])-int(bool(r["observed_outcome"])))**2 for r in values)/len(values) if values else None
    return {"schema_version":"geowatch-frozen-forecast-bank-summary-v1","count":len(values),"by_horizon":dict(sorted(by_h.items())),"by_outcome":dict(sorted(by_tag.items())),"brier_score":round(brier,6) if brier is not None else None,"supported_outcomes":list(SUPPORTED_OUTCOMES),"horizons":list(FORECAST_HORIZONS),"benchmark_not_prospective_track_record":True}


def _d(value: str)->date: return date.fromisoformat(str(value)[:10])

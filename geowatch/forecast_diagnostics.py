from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def reliability_diagram(rows: Iterable[dict], *, bins: int=10) -> dict:
    resolved=[r for r in rows if r.get("status")=="resolved" and r.get("observed_outcome") in (0,1) and isinstance(r.get("probability"),(int,float))]
    buckets=[]
    for i in range(bins):
        low=i/bins; high=(i+1)/bins
        group=[r for r in resolved if low<=float(r["probability"])<(high if i<bins-1 else high+1e-12)]
        buckets.append({"bin":i,"low":low,"high":high,"count":len(group),"mean_probability":round(sum(float(r["probability"]) for r in group)/len(group),6) if group else None,"observed_rate":round(sum(int(r["observed_outcome"]) for r in group)/len(group),6) if group else None})
    return {"schema_version":"geowatch-forecast-reliability-diagram-v1","resolved_count":len(resolved),"bins":buckets,"requires_sufficient_resolution_before_interpretation":True}


def compare_to_baseline(rows: Iterable[dict], baseline: dict[str,float]) -> dict:
    resolved=[r for r in rows if r.get("status")=="resolved" and r.get("observed_outcome") in (0,1)]
    paired=[]
    for r in resolved:
        outcome=str(r.get("outcome")); bp=baseline.get(outcome)
        if bp is None: continue
        y=int(r["observed_outcome"]); mp=float(r["probability"])
        paired.append({"forecast_id":r.get("forecast_id"),"model_brier":(mp-y)**2,"baseline_brier":(float(bp)-y)**2,"outcome":outcome,"horizon_days":r.get("horizon_days")})
    if not paired: return {"schema_version":"geowatch-forecast-baseline-comparison-v1","count":0,"model_brier":None,"baseline_brier":None,"skill_score":None}
    model=sum(r["model_brier"] for r in paired)/len(paired); base=sum(r["baseline_brier"] for r in paired)/len(paired)
    skill=1-(model/base) if base>0 else None
    return {"schema_version":"geowatch-forecast-baseline-comparison-v1","count":len(paired),"model_brier":round(model,6),"baseline_brier":round(base,6),"skill_score":round(skill,6) if skill is not None else None,"positive_skill_means_better_than_baseline":True}


def error_decomposition(rows: Iterable[dict]) -> dict:
    resolved=[r for r in rows if r.get("status")=="resolved" and r.get("observed_outcome") in (0,1)]
    groups=defaultdict(list)
    for r in resolved: groups[(str(r.get("outcome")),int(r.get("horizon_days") or 0))].append(r)
    cells=[]
    for (outcome,horizon),vals in sorted(groups.items()):
        brier=sum((float(r["probability"])-int(r["observed_outcome"]))**2 for r in vals)/len(vals)
        avg_p=sum(float(r["probability"]) for r in vals)/len(vals); rate=sum(int(r["observed_outcome"]) for r in vals)/len(vals)
        cells.append({"outcome":outcome,"horizon_days":horizon,"count":len(vals),"brier":round(brier,6),"mean_probability":round(avg_p,6),"observed_rate":round(rate,6),"calibration_gap":round(avg_p-rate,6)})
    return {"schema_version":"geowatch-forecast-error-decomposition-v1","resolved_count":len(resolved),"cells":cells,"diagnostic_not_causal_attribution":True}

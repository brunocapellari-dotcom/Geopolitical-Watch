from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def objective_resolution(row: dict, episode_timeline: Iterable[dict], *, resolved_at: str) -> dict:
    target=str(row.get("outcome")); deadline=str(row.get("resolution_deadline")); created=str(row.get("created_at"))
    relevant=[r for r in episode_timeline if str(r.get("episode_id"))==str(row.get("episode_id")) and str(r.get("observed_at") or "")>=created and str(r.get("observed_at") or "")<=deadline]
    mapping={"escalation":"escalating","deescalation":"deescalating","ceasefire":"ceasefire"}; target_state=mapping.get(target)
    observed=any(str(r.get("state"))==target_state for r in relevant) if target_state else False
    return {**row,"status":"resolved","observed_outcome":1 if observed else 0,"resolved_at":resolved_at,"resolution_method":"objective_state_timeline","resolution_evidence_count":len(relevant),"resolution_definition_version":"v1"}


def reliability_diagram(rows: Iterable[dict], *, bins: int=10) -> dict:
    vals=[r for r in rows if r.get("status")=="resolved" and r.get("observed_outcome") in (0,1) and isinstance(r.get("probability"),(int,float))]
    buckets=[[] for _ in range(bins)]
    for r in vals:
        idx=min(bins-1,max(0,int(float(r["probability"])*bins))); buckets[idx].append(r)
    out=[]
    for i,group in enumerate(buckets):
        if not group: continue
        mean_p=sum(float(r["probability"]) for r in group)/len(group); freq=sum(int(r["observed_outcome"]) for r in group)/len(group)
        out.append({"bin":i,"count":len(group),"mean_probability":round(mean_p,6),"observed_frequency":round(freq,6),"calibration_gap":round(mean_p-freq,6)})
    return {"schema_version":"geowatch-reliability-diagram-v1","resolved_count":len(vals),"bins":out,"prospective_only":True}


def brier_skill(rows: Iterable[dict], *, climatology: float | None=None) -> dict:
    vals=[r for r in rows if r.get("status")=="resolved" and r.get("observed_outcome") in (0,1) and isinstance(r.get("probability"),(int,float))]
    if not vals: return {"schema_version":"geowatch-brier-skill-v1","count":0,"brier":None,"climatology":None,"baseline_brier":None,"skill":None}
    observed=sum(int(r["observed_outcome"]) for r in vals)/len(vals); clim=observed if climatology is None else float(climatology)
    brier=sum((float(r["probability"])-int(r["observed_outcome"]))**2 for r in vals)/len(vals); base=sum((clim-int(r["observed_outcome"]))**2 for r in vals)/len(vals); skill=1-(brier/base) if base>0 else None
    return {"schema_version":"geowatch-brier-skill-v1","count":len(vals),"brier":round(brier,6),"climatology":round(clim,6),"baseline_brier":round(base,6),"skill":round(skill,6) if skill is not None else None,"positive_skill_beats_baseline":skill is not None and skill>0}


def by_horizon_skill(rows: Iterable[dict]) -> dict:
    groups=defaultdict(list)
    for r in rows:
        if r.get("status")=="resolved": groups[str(r.get("horizon_days"))].append(r)
    return {"schema_version":"geowatch-horizon-skill-v1","horizons":{h:brier_skill(vals) for h,vals in sorted(groups.items(),key=lambda x:int(x[0] or 0))}}


def largest_misses(rows: Iterable[dict], *, limit: int=20) -> list[dict]:
    vals=[]
    for r in rows:
        if r.get("status")!="resolved" or r.get("observed_outcome") not in (0,1) or not isinstance(r.get("probability"),(int,float)): continue
        error=abs(float(r["probability"])-int(r["observed_outcome"]))
        vals.append({**r,"absolute_probability_error":round(error,6),"squared_error":round(error*error,6)})
    return sorted(vals,key=lambda r:r["squared_error"],reverse=True)[:limit]


def forecast_miss_postmortems(rows: Iterable[dict], *, threshold: float=0.65, limit: int=20) -> list[dict]:
    out=[]
    for r in largest_misses(rows,limit=limit*2):
        if r["absolute_probability_error"]<threshold: continue
        out.append({"incident_id":"forecast_"+str(r.get("forecast_id")),"incident_type":"forecast_miss","severity":"high","detected_at":r.get("resolved_at"),"expected_behavior":f"forecast probability {r.get('probability')} for {r.get('outcome')}","observed_behavior":f"resolved outcome {r.get('observed_outcome')}","evidence":[{"forecast_id":r.get("forecast_id"),"episode_id":r.get("episode_id"),"information_cutoff":r.get("information_cutoff"),"resolution_method":r.get("resolution_method")}],"root_cause":None,"status":"open","automatic_model_change_forbidden":True})
        if len(out)>=limit: break
    return out

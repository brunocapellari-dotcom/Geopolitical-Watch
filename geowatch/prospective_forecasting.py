from __future__ import annotations

import hashlib
from datetime import datetime,timedelta,timezone
from typing import Iterable

HORIZONS=(1,7,30,90)


def _dt(value: str | None) -> datetime:
    if not value: return datetime.now(timezone.utc)
    row=datetime.fromisoformat(str(value).replace("Z","+00:00")); return row if row.tzinfo else row.replace(tzinfo=timezone.utc)


def create_prospective_forecasts(episodes: Iterable[dict], *, created_at: str, baseline_probabilities: dict[str,float] | None=None) -> list[dict]:
    created=_dt(created_at); baseline=baseline_probabilities or {"escalation":0.20,"deescalation":0.20,"ceasefire":0.10}
    rows=[]
    for ep in episodes:
        eid=ep.get("episode_id")
        if not eid: continue
        state=str(ep.get("state") or "unknown")
        strength=(ep.get("evidence_strength") or {}).get("overall_index",ep.get("evidence_strength_index"))
        for outcome,p in baseline.items():
            for horizon in HORIZONS:
                raw=f"{eid}|{created.isoformat()}|{outcome}|{horizon}"
                rows.append({
                    "forecast_id":"pf_"+hashlib.sha256(raw.encode()).hexdigest()[:24],"episode_id":eid,"outcome":outcome,
                    "horizon_days":horizon,"created_at":created.isoformat(),"information_cutoff":created.isoformat(),
                    "resolution_deadline":(created+timedelta(days=horizon)).isoformat(),"probability":round(float(p),6),
                    "status":"open","episode_state_at_creation":state,"evidence_strength_at_creation":strength,
                    "model_id":"baseline-v1","probability_does_not_change_evidence_strength":True,
                })
    return rows


def append_forecast_ledger(ledger: dict | None, forecasts: Iterable[dict]) -> dict:
    rows=list((ledger or {}).get("forecasts") or []); known={r.get("forecast_id") for r in rows}
    for row in forecasts:
        if row.get("forecast_id") not in known: rows.append(dict(row)); known.add(row.get("forecast_id"))
    return {"schema_version":"geowatch-prospective-forecast-ledger-v1","forecast_count":len(rows),"forecasts":rows,"append_only_probabilities":True}


def resolve_forecasts(ledger: dict, episode_states: dict[str,dict], *, resolved_at: str) -> dict:
    now=_dt(resolved_at); rows=[]
    for row in ledger.get("forecasts",[]):
        item=dict(row)
        if item.get("status")!="open": rows.append(item); continue
        deadline=_dt(item.get("resolution_deadline")); ep=episode_states.get(str(item.get("episode_id")),{})
        state=str(ep.get("state") or "")
        target=str(item.get("outcome"))
        observed=(target=="escalation" and state=="escalating") or (target=="deescalation" and state=="deescalating") or (target=="ceasefire" and state=="ceasefire")
        if observed or now>=deadline:
            item["status"]="resolved"; item["observed_outcome"]=1 if observed else 0; item["resolved_at"]=now.isoformat()
        rows.append(item)
    return {"schema_version":"geowatch-prospective-forecast-ledger-v1","forecast_count":len(rows),"forecasts":rows,"original_probabilities_preserved":True}


def score_resolved_forecasts(ledger: dict) -> dict:
    vals=[r for r in ledger.get("forecasts",[]) if r.get("status")=="resolved" and r.get("observed_outcome") in (0,1)]
    if not vals: return {"schema_version":"geowatch-prospective-forecast-score-v1","resolved_count":0,"brier_score":None,"by_horizon":{}}
    def score(rows): return sum((float(r["probability"])-int(r["observed_outcome"]))**2 for r in rows)/len(rows)
    by_h={}
    for h in HORIZONS:
        group=[r for r in vals if int(r.get("horizon_days") or 0)==h]
        if group: by_h[str(h)]={"count":len(group),"brier_score":round(score(group),6)}
    return {"schema_version":"geowatch-prospective-forecast-score-v1","resolved_count":len(vals),"brier_score":round(score(vals),6),"by_horizon":by_h,"prospective_track_record":True}

from __future__ import annotations

from datetime import datetime,timedelta,timezone
from typing import Iterable


def _dt(value: str | None) -> datetime | None:
    if not value: return None
    try:
        row=datetime.fromisoformat(str(value).replace("Z","+00:00")); return row if row.tzinfo else row.replace(tzinfo=timezone.utc)
    except ValueError: return None


def error_budget(*, availability_target: float, observed_availability: float | None) -> dict:
    allowed=max(0.0,1.0-float(availability_target))
    if observed_availability is None:
        return {"allowed_unavailability":allowed,"observed_unavailability":None,"budget_consumed_ratio":None,"budget_remaining_ratio":None,"insufficient_data":True}
    observed=max(0.0,1.0-float(observed_availability))
    consumed=(observed/allowed) if allowed>0 else (0.0 if observed==0 else float("inf"))
    remaining=1.0-consumed if consumed!=float("inf") else float("-inf")
    return {"allowed_unavailability":round(allowed,6),"observed_unavailability":round(observed,6),"budget_consumed_ratio":round(consumed,6) if consumed not in (float("inf"),float("-inf")) else str(consumed),"budget_remaining_ratio":round(remaining,6) if remaining not in (float("inf"),float("-inf")) else str(remaining),"insufficient_data":False}


def burn_rate(observations: Iterable[dict], *, source_id: str, availability_target: float, as_of: str, short_hours: int=6, long_hours: int=24*7) -> dict:
    now=_dt(as_of) or datetime.now(timezone.utc); rows=[r for r in observations if r.get("source_id")==source_id and _dt(r.get("observed_at"))]
    allowed=max(1e-9,1.0-float(availability_target))
    def window(hours:int):
        cutoff=now-timedelta(hours=hours); vals=[r for r in rows if (_dt(r.get("observed_at")) or now)>=cutoff]
        if not vals: return {"hours":hours,"observations":0,"availability":None,"burn_rate":None}
        ok=sum(r.get("result_class")=="success" for r in vals); avail=ok/len(vals); unavail=1-avail
        return {"hours":hours,"observations":len(vals),"availability":round(avail,6),"burn_rate":round(unavail/allowed,6)}
    short=window(short_hours); long=window(long_hours)
    fast_alert=bool(short["burn_rate"] is not None and long["burn_rate"] is not None and short["burn_rate"]>=14.4 and long["burn_rate"]>=6.0)
    slow_alert=bool(short["burn_rate"] is not None and long["burn_rate"] is not None and short["burn_rate"]>=6.0 and long["burn_rate"]>=3.0)
    return {"schema_version":"geowatch-error-budget-burn-v1","source_id":source_id,"availability_target":availability_target,"short_window":short,"long_window":long,"fast_burn_alert":fast_alert,"slow_burn_alert":slow_alert,"thresholds_are_initial_operational_policy":True}


def reliability_score(*, availability_30d: float | None, freshness_slo_passed: bool | None, open_incident: bool, structural_failures_30d: int=0) -> dict:
    if availability_30d is None:
        return {"score":None,"class":"insufficient_history","operational_not_intelligence_quality":True}
    score=100.0*max(0.0,min(1.0,availability_30d))
    if freshness_slo_passed is False: score-=15
    if open_incident: score-=20
    score-=min(30,5*max(0,int(structural_failures_30d)))
    score=max(0.0,min(100.0,score))
    cls="excellent" if score>=99 else "good" if score>=95 else "degraded" if score>=80 else "poor"
    return {"score":round(score,2),"class":cls,"operational_not_intelligence_quality":True}


def stale_coverage_alerts(source_summary: dict, slo_config: dict) -> list[dict]:
    cfg={r.get("source_id"):r for r in slo_config.get("sources",[])}; alerts=[]
    for row in source_summary.get("sources",[]):
        sid=row.get("source_id"); target=cfg.get(sid,{}).get("max_freshness_hours"); actual=row.get("freshness_hours")
        if target is None or actual is None: continue
        if float(actual)>float(target):
            alerts.append({"alert_type":"stale_coverage","source_id":sid,"freshness_hours":actual,"target_hours":target,"severity":"high" if float(actual)>=2*float(target) else "medium","event_evidence":False})
    return alerts

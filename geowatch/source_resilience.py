from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

TRANSIENT_TOKENS=("429","timeout","timed out","502","503","504","connection","temporarily unavailable")


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        row=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return row if row.tzinfo else row.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def source_result_class(row: dict) -> str:
    if row.get("status") == "ok": return "success"
    text=str(row.get("error") or "").casefold()
    return "transient_failure" if any(token in text for token in TRANSIENT_TOKENS) else "structural_failure"


def append_source_history(history: dict | None, *, generated_at: str, source_results: Iterable[dict], coverage: dict | None=None, retention_days: int=365) -> dict:
    rows=list((history or {}).get("observations") or [])
    coverage_map={r.get("source_id"):r for r in (coverage or {}).get("sources",[])}
    for result in source_results:
        sid=result.get("source_id")
        c=coverage_map.get(sid,{})
        rows.append({
            "observed_at":generated_at,"source_id":sid,"result_class":source_result_class(result),
            "status":result.get("status"),"error":result.get("error"),"records":result.get("records"),
            "latest_reference_at":c.get("last_reference_in_bounded_sample"),
        })
    cutoff=(_dt(generated_at) or datetime.now(timezone.utc))-timedelta(days=max(1,retention_days))
    rows=[r for r in rows if (_dt(r.get("observed_at")) or cutoff)>=cutoff]
    return {"schema_version":"geowatch-source-history-v1","retention_days":retention_days,"observation_count":len(rows),"observations":rows,"operational_history_not_event_evidence":True}


def summarize_source_history(history: dict, *, as_of: str | None=None, slo_config: dict | None=None) -> dict:
    now=_dt(as_of) or datetime.now(timezone.utc)
    slo={r["source_id"]:r for r in (slo_config or {}).get("sources",[])}
    by_source: dict[str,list[dict]]={}
    for row in history.get("observations",[]): by_source.setdefault(str(row.get("source_id")),[]).append(row)
    sources=[]
    for sid,values in sorted(by_source.items()):
        ordered=sorted(values,key=lambda r:str(r.get("observed_at") or "")); total=len(ordered); ok=sum(r.get("result_class")=="success" for r in ordered)
        incidents=[]; open_start=None; last_recovery=None
        for row in ordered:
            t=_dt(row.get("observed_at")); success=row.get("result_class")=="success"
            if not success and open_start is None: open_start=t
            if success and open_start is not None and t is not None:
                incidents.append((open_start,t)); last_recovery=t; open_start=None
        if open_start is not None: incidents.append((open_start,None))
        durations=[(end-start).total_seconds()/60 for start,end in incidents if start and end]
        latest_ref=max((_dt(r.get("latest_reference_at")) for r in ordered if _dt(r.get("latest_reference_at"))),default=None)
        freshness=(now-latest_ref).total_seconds()/3600 if latest_ref else None
        cfg=slo.get(sid,{})
        max_fresh=cfg.get("max_freshness_hours"); min_avail=cfg.get("monthly_availability_target")
        availability=(ok/total) if total else None
        sources.append({
            "source_id":sid,"observations":total,"successful":ok,"availability_ratio":round(availability,6) if availability is not None else None,
            "incident_count":len(incidents),"open_incident":bool(incidents and incidents[-1][1] is None),
            "mttr_minutes":round(sum(durations)/len(durations),3) if durations else None,"last_recovery_at":last_recovery.isoformat() if last_recovery else None,
            "latest_reference_at":latest_ref.isoformat() if latest_ref else None,"freshness_hours":round(freshness,3) if freshness is not None else None,
            "freshness_slo_passed":None if max_fresh is None or freshness is None else freshness<=float(max_fresh),
            "availability_slo_passed":None if min_avail is None or availability is None else availability>=float(min_avail),
        })
    return {"schema_version":"geowatch-source-resilience-summary-v1","as_of":now.isoformat(),"sources":sources,"provider_availability_separate_from_internal_system_health":True}


@dataclass(frozen=True)
class CircuitDecision:
    source_id: str
    state: str
    allow_request: bool
    reason: str
    retry_after_seconds: int


def circuit_breaker(source_id: str, observations: Iterable[dict], *, failure_threshold: int=3, cooldown_seconds: int=900, now: str | None=None) -> CircuitDecision:
    current=_dt(now) or datetime.now(timezone.utc)
    rows=sorted([r for r in observations if r.get("source_id")==source_id],key=lambda r:str(r.get("observed_at") or ""))
    consecutive=0; last_failure_at=None
    for row in reversed(rows):
        if row.get("result_class")=="success": break
        consecutive+=1; last_failure_at=last_failure_at or _dt(row.get("observed_at"))
    if consecutive<failure_threshold:
        return CircuitDecision(source_id,"closed",True,"below_failure_threshold",0)
    elapsed=(current-last_failure_at).total_seconds() if last_failure_at else 0
    if elapsed>=cooldown_seconds:
        return CircuitDecision(source_id,"half_open",True,"cooldown_elapsed_probe_allowed",0)
    remaining=max(1,int(cooldown_seconds-elapsed))
    return CircuitDecision(source_id,"open",False,"consecutive_provider_failures",remaining)

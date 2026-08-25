from __future__ import annotations

from datetime import datetime,timezone
from typing import Iterable


def _dt(value: str) -> datetime:
    row=datetime.fromisoformat(str(value).replace("Z","+00:00")); return row if row.tzinfo else row.replace(tzinfo=timezone.utc)


def leading_indicator_metrics(signals: Iterable[dict], outcomes: Iterable[dict], *, max_lead_days: int=90) -> dict:
    outs=list(outcomes); rows=[]
    for signal in signals:
        sid=signal.get("episode_id"); st=_dt(signal["observed_at"])
        candidates=[]
        for out in outs:
            if out.get("episode_id")!=sid: continue
            ot=_dt(out["observed_at"]); delta=(ot-st).total_seconds()/86400
            if 0<=delta<=max_lead_days: candidates.append((delta,out))
        if candidates:
            delta,out=min(candidates,key=lambda x:x[0])
            rows.append({"signal_type":signal.get("signal_type"),"episode_id":sid,"lead_days":round(delta,4),"outcome_type":out.get("outcome_type"),"true_lead":True})
        else:
            rows.append({"signal_type":signal.get("signal_type"),"episode_id":sid,"lead_days":None,"outcome_type":None,"true_lead":False})
    matched=[r for r in rows if r["true_lead"]]
    false_positive_rate=1-(len(matched)/len(rows)) if rows else None
    mean=sum(r["lead_days"] for r in matched)/len(matched) if matched else None
    return {"schema_version":"geowatch-leading-indicator-eval-v1","signal_count":len(rows),"matched_count":len(matched),"mean_lead_days":round(mean,4) if mean is not None else None,"false_positive_rate":round(false_positive_rate,6) if false_positive_rate is not None else None,"rows":rows,"requires_prospective_timestamps":True}


def make_postmortem(*, incident_id: str, incident_type: str, detected_at: str, severity: str, evidence: list[dict], expected_behavior: str, observed_behavior: str, root_cause: str | None=None) -> dict:
    return {
        "schema_version":"geowatch-postmortem-v1","incident_id":incident_id,"incident_type":incident_type,"severity":severity,"detected_at":detected_at,
        "expected_behavior":expected_behavior,"observed_behavior":observed_behavior,"evidence":evidence,"root_cause":root_cause,
        "corrective_actions":[],"learning_proposals":[],"status":"open","automatic_model_change_forbidden":True,
    }


def postmortem_gate(incidents: Iterable[dict], postmortems: Iterable[dict], *, material_severities: tuple[str,...]=("high","critical")) -> dict:
    required=[r for r in incidents if str(r.get("severity")) in material_severities]
    completed={p.get("incident_id") for p in postmortems if p.get("status") in {"completed","closed"} and p.get("root_cause")}
    missing=[r.get("incident_id") for r in required if r.get("incident_id") not in completed]
    return {"schema_version":"geowatch-postmortem-gate-v1","material_incidents":len(required),"completed_postmortems":len(required)-len(missing),"missing":missing,"passed":not missing,"material_failures_require_postmortem":True}

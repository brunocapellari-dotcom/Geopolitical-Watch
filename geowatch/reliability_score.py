from __future__ import annotations


def source_reliability(row: dict, *, availability_target: float | None=None) -> dict:
    availability=row.get("availability_ratio")
    freshness_pass=row.get("freshness_slo_passed")
    open_incident=bool(row.get("open_incident"))
    if availability is None:
        score=None
    else:
        score=float(availability)
        if freshness_pass is False: score*=0.75
        if open_incident: score*=0.8
        score=round(max(0.0,min(1.0,score)),6)
    target=availability_target
    budget_remaining=None
    if availability is not None and target is not None and target<1:
        allowed=1-float(target); used=max(0.0,1-float(availability)); budget_remaining=round(max(0.0,1-(used/allowed if allowed else 1.0)),6)
    return {
        "schema_version":"geowatch-source-reliability-v1","source_id":row.get("source_id"),
        "operational_reliability_score":score,"availability_ratio":availability,
        "freshness_slo_passed":freshness_pass,"open_incident":open_incident,
        "error_budget_remaining_ratio":budget_remaining,"accuracy_not_measured_here":True,
    }


def reliability_dashboard(source_summary: dict, slo_config: dict) -> dict:
    cfg={r.get("source_id"):r for r in slo_config.get("sources",[])}
    rows=[]
    for row in source_summary.get("sources",[]):
        target=(cfg.get(row.get("source_id")) or {}).get("monthly_availability_target")
        rows.append(source_reliability(row,availability_target=target))
    known=[r["operational_reliability_score"] for r in rows if r["operational_reliability_score"] is not None]
    return {"schema_version":"geowatch-reliability-dashboard-v1","sources":rows,"portfolio_operational_reliability":round(sum(known)/len(known),6) if known else None,"provider_reliability_not_intelligence_quality":True}

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .forecasting import forecast_summary


def validate_backtest_row(row: dict) -> list[str]:
    issues=[]
    created=row.get("created_at"); resolved=row.get("resolved_at")
    if not created: issues.append("missing_created_at")
    if not resolved: issues.append("missing_resolved_at")
    if created and resolved and _dt(created)>=_dt(resolved): issues.append("forecast_not_strictly_before_resolution")
    p=row.get("probability")
    if p is None or not 0<=float(p)<=1: issues.append("invalid_probability")
    if row.get("outcome") not in (0,1): issues.append("invalid_outcome")
    if not row.get("information_cutoff"): issues.append("missing_information_cutoff")
    if row.get("information_cutoff") and created and _dt(row["information_cutoff"])>_dt(created): issues.append("cutoff_after_forecast_creation")
    return issues


def evaluate_temporal_backtest(rows: Iterable[dict]) -> dict:
    valid=[]; rejected=[]
    for row in rows:
        issues=validate_backtest_row(row)
        if issues: rejected.append({"forecast_id":row.get("forecast_id"),"issues":issues})
        else: valid.append({**row,"status":"resolved"})
    by_horizon={}
    for row in valid:
        key=str(row.get("horizon_days") or "unknown"); by_horizon.setdefault(key,[]).append(row)
    return {
        "schema_version":"geowatch-temporal-backtest-v1",
        "overall":forecast_summary(valid),
        "by_horizon":{key:forecast_summary(values) for key,values in sorted(by_horizon.items())},
        "accepted":len(valid),"rejected":len(rejected),"rejections":rejected,
        "no_lookahead_required":True,
    }


def rolling_origin_windows(start_year:int,end_year:int,*,train_years:int=5)->list[dict]:
    if end_year<=start_year or train_years<1: return []
    return [{"train_start":f"{start_year}-01-01","train_end":f"{year-1}-12-31","test_start":f"{year}-01-01","test_end":f"{year}-12-31"} for year in range(start_year+train_years,end_year+1)]


def _dt(value:str)->datetime:
    return datetime.fromisoformat(value.replace("Z","+00:00"))

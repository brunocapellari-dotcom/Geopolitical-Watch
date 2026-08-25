from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .historical_backtest import evaluate_temporal_backtest


def classification_metrics(rows: Iterable[dict]) -> dict:
    values=list(rows); tp=fp=tn=fn=0
    for row in values:
        predicted=bool(row.get("predicted")); observed=bool(row.get("observed"))
        if predicted and observed: tp+=1
        elif predicted and not observed: fp+=1
        elif not predicted and observed: fn+=1
        else: tn+=1
    precision=tp/(tp+fp) if tp+fp else None; recall=tp/(tp+fn) if tp+fn else None; fpr=fp/(fp+tn) if fp+tn else None
    return {"count":len(values),"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":round(precision,4) if precision is not None else None,"recall":round(recall,4) if recall is not None else None,"false_positive_rate":round(fpr,4) if fpr is not None else None}


def _group(rows:list[dict],field:str)->dict[str,list[dict]]:
    grouped:dict[str,list[dict]]=defaultdict(list)
    for row in rows:
        value=row.get(field)
        if isinstance(value,(list,tuple,set)):
            key="+".join(sorted(str(v) for v in value if v)) or "unknown"
        else: key=str(value or "unknown")
        grouped[key].append(row)
    return grouped


def _forecast_slices(rows:list[dict],field:str)->dict[str,dict]:
    return {key:evaluate_temporal_backtest(values) for key,values in sorted(_group(rows,field).items()) if values}


def _classification_slices(rows:list[dict],field:str)->dict[str,dict]:
    return {key:classification_metrics(values) for key,values in sorted(_group(rows,field).items())}


def rolling_oos_report(*, forecasts: Iterable[dict]=(), alerts: Iterable[dict]=(), convergence: Iterable[dict]=()) -> dict:
    forecast_rows=list(forecasts); alert_rows=list(alerts); convergence_rows=list(convergence)
    by_year:dict[str,dict[str,list[dict]]]=defaultdict(lambda:{"forecasts":[],"alerts":[],"convergence":[]})
    for row in forecast_rows: by_year[str(row.get("created_at","unknown"))[:4]]["forecasts"].append(row)
    for row in alert_rows: by_year[str(row.get("at") or row.get("created_at") or "unknown")[:4]]["alerts"].append(row)
    for row in convergence_rows: by_year[str(row.get("at") or row.get("reference_at") or "unknown")[:4]]["convergence"].append(row)
    windows=[]
    for year,parts in sorted(by_year.items()):
        windows.append({"year":year,"forecast":evaluate_temporal_backtest(parts["forecasts"]) if parts["forecasts"] else None,"alerts":classification_metrics(parts["alerts"]),"convergence":classification_metrics(parts["convergence"])})
    return {
        "schema_version":"geowatch-rolling-oos-report-v2","windows":windows,
        "overall_alerts":classification_metrics(alert_rows),"overall_convergence":classification_metrics(convergence_rows),
        "forecast_backtest":evaluate_temporal_backtest(forecast_rows),
        "by_region":{"forecasts":_forecast_slices(forecast_rows,"region"),"alerts":_classification_slices(alert_rows,"region"),"convergence":_classification_slices(convergence_rows,"region")},
        "by_source_mix":{"forecasts":_forecast_slices(forecast_rows,"source_mix"),"alerts":_classification_slices(alert_rows,"source_mix"),"convergence":_classification_slices(convergence_rows,"source_mix")},
        "methodology_notes":[
            "Evaluation rows must be generated from information available before outcome resolution.",
            "Synthetic fixtures and real-world source-backed corpora must be reported separately.",
            "A good aggregate score cannot hide unstable yearly, regional or source-mix slices.",
            "Unknown region/source_mix is retained instead of silently discarded.",
        ],
    }

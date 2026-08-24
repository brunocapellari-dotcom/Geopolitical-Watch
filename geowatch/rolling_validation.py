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
    precision=tp/(tp+fp) if tp+fp else None; recall=tp/(tp+fn) if tp+fn else None
    fpr=fp/(fp+tn) if fp+tn else None
    return {"count":len(values),"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":round(precision,4) if precision is not None else None,"recall":round(recall,4) if recall is not None else None,"false_positive_rate":round(fpr,4) if fpr is not None else None}


def rolling_oos_report(*, forecasts: Iterable[dict]=(), alerts: Iterable[dict]=(), convergence: Iterable[dict]=()) -> dict:
    forecast_rows=list(forecasts); alert_rows=list(alerts); convergence_rows=list(convergence)
    by_year: dict[str, dict[str,list[dict]]] = defaultdict(lambda:{"forecasts":[],"alerts":[],"convergence":[]})
    for row in forecast_rows:
        year=str(row.get("created_at", "unknown"))[:4]; by_year[year]["forecasts"].append(row)
    for row in alert_rows:
        year=str(row.get("at") or row.get("created_at") or "unknown")[:4]; by_year[year]["alerts"].append(row)
    for row in convergence_rows:
        year=str(row.get("at") or row.get("reference_at") or "unknown")[:4]; by_year[year]["convergence"].append(row)
    windows=[]
    for year, parts in sorted(by_year.items()):
        windows.append({
            "year":year,
            "forecast":evaluate_temporal_backtest(parts["forecasts"]) if parts["forecasts"] else None,
            "alerts":classification_metrics(parts["alerts"]),
            "convergence":classification_metrics(parts["convergence"]),
        })
    return {
        "schema_version":"geowatch-rolling-oos-report-v1",
        "windows":windows,
        "overall_alerts":classification_metrics(alert_rows),
        "overall_convergence":classification_metrics(convergence_rows),
        "forecast_backtest":evaluate_temporal_backtest(forecast_rows),
        "methodology_notes":["Evaluation rows must be generated from information available before outcome resolution.","Synthetic fixtures and real-world source-backed corpora must be reported separately.","A good aggregate score cannot hide unstable yearly windows."],
    }

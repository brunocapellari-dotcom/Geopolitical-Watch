from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .gold_calibration import evaluate_holdout,threshold_scan


def _year(row: dict) -> int | None:
    for key in ("reference_year","year","end_year","start_year"):
        try:
            if row.get(key) not in (None,""): return int(str(row[key])[:4])
        except ValueError: pass
    for key in ("reference_at","reviewed_at","end","start"):
        value=str(row.get(key) or "")
        if len(value)>=4 and value[:4].isdigit(): return int(value[:4])
    return None


def rolling_gold_oos(rows: Iterable[dict], *, task_type: str, positive_label: str, min_train: int=30, min_test: int=10) -> dict:
    vals=[dict(r) for r in rows if r.get("human_gold") is True and r.get("task_type")==task_type and isinstance(r.get("machine_score"),(int,float)) and _year(r) is not None]
    years=sorted({_year(r) for r in vals if _year(r) is not None}); folds=[]
    for test_year in years:
        train=[r for r in vals if (_year(r) or 9999)<test_year]; test=[r for r in vals if _year(r)==test_year]
        if len(train)<min_train or len(test)<min_test:
            folds.append({"test_year":test_year,"train_count":len(train),"test_count":len(test),"status":"insufficient_samples"}); continue
        scan=threshold_scan(train,positive_label=positive_label); best=(scan.get("best") or {}).get("threshold")
        if best is None:
            folds.append({"test_year":test_year,"train_count":len(train),"test_count":len(test),"status":"no_train_threshold"}); continue
        folds.append({"test_year":test_year,"train_count":len(train),"test_count":len(test),"status":"evaluated","selected_threshold":best,"test_metrics":evaluate_holdout(test,positive_label=positive_label,threshold=float(best))})
    evaluated=[f for f in folds if f.get("status")=="evaluated"]
    return {"schema_version":"geowatch-rolling-gold-oos-v1","task_type":task_type,"fold_count":len(folds),"evaluated_fold_count":len(evaluated),"folds":folds,"only_past_years_train_each_fold":True,"test_year_never_selects_threshold":True}


def segmented_gold_oos(rows: Iterable[dict], *, task_type: str, positive_label: str) -> dict:
    vals=[dict(r) for r in rows if r.get("human_gold") is True and r.get("task_type")==task_type]
    groups=defaultdict(list)
    for r in vals:
        region=str(r.get("region") or "unknown"); mix="+".join(sorted(str(x) for x in (r.get("source_mix") or []))) or "unknown"; groups[(region,mix)].append(r)
    segments=[]
    for (region,mix),group in sorted(groups.items()):
        result=rolling_gold_oos(group,task_type=task_type,positive_label=positive_label)
        segments.append({"region":region,"source_mix":mix,"sample_count":len(group),"oos":result})
    return {"schema_version":"geowatch-segmented-gold-oos-v1","segments":segments,"human_gold_only":True}

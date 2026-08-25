from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Iterable


def deterministic_gold_split(rows: Iterable[dict], *, holdout_fraction: float=0.2, salt: str="geowatch-gold-v1") -> dict:
    train=[]; holdout=[]
    for row in rows:
        if row.get("human_gold") is not True: continue
        cid=str(row.get("candidate_id") or row.get("episode_id") or "")
        bucket=int(hashlib.sha256(f"{salt}|{cid}".encode()).hexdigest()[:8],16)/0xFFFFFFFF
        (holdout if bucket<holdout_fraction else train).append(dict(row))
    return {"schema_version":"geowatch-gold-split-v1","train":train,"holdout":holdout,"train_count":len(train),"holdout_count":len(holdout),"holdout_fraction":holdout_fraction,"split_is_deterministic":True}


def threshold_scan(rows: Iterable[dict], *, positive_label: str, thresholds: Iterable[float]|None=None) -> dict:
    vals=[r for r in rows if r.get("human_gold") is True and isinstance(r.get("machine_score"),(int,float)) and r.get("human_label") is not None]
    thresholds=list(thresholds or [i/20 for i in range(1,20)]); scans=[]
    for t in thresholds:
        tp=fp=tn=fn=0
        for r in vals:
            pred=float(r["machine_score"])>=t; actual=str(r["human_label"])==positive_label
            if pred and actual: tp+=1
            elif pred: fp+=1
            elif actual: fn+=1
            else: tn+=1
        precision=tp/(tp+fp) if tp+fp else None; recall=tp/(tp+fn) if tp+fn else None; f1=(2*precision*recall/(precision+recall)) if precision is not None and recall is not None and precision+recall else None
        scans.append({"threshold":t,"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":precision,"recall":recall,"f1":f1})
    best=max((r for r in scans if r["f1"] is not None),key=lambda r:r["f1"],default=None)
    return {"schema_version":"geowatch-gold-threshold-scan-v1","count":len(vals),"positive_label":positive_label,"best":best,"scans":scans,"gold_only":True,"threshold_not_auto_promoted":True}


def segmented_thresholds(rows: Iterable[dict], *, positive_label: str, min_samples: int=30) -> dict:
    groups=defaultdict(list)
    for r in rows:
        if r.get("human_gold") is not True: continue
        region=str(r.get("region") or "unknown"); mix="+".join(sorted(str(x) for x in (r.get("source_mix") or []))) or "unknown"
        groups[(region,mix)].append(r)
    out=[]
    for (region,mix),vals in sorted(groups.items()):
        scan=threshold_scan(vals,positive_label=positive_label)
        eligible=len(vals)>=min_samples and scan.get("best") is not None
        out.append({"region":region,"source_mix":mix,"sample_count":len(vals),"eligible":eligible,"candidate_threshold":scan.get("best",{}).get("threshold") if eligible else None,"candidate_metrics":scan.get("best") if eligible else None})
    return {"schema_version":"geowatch-segmented-gold-calibration-v1","minimum_samples":min_samples,"segments":out,"candidate_thresholds_require_independent_validation":True}


def evaluate_holdout(rows: Iterable[dict], *, positive_label: str, threshold: float) -> dict:
    vals=[r for r in rows if r.get("human_gold") is True and isinstance(r.get("machine_score"),(int,float))]
    tp=fp=tn=fn=0
    for r in vals:
        pred=float(r["machine_score"])>=threshold; actual=str(r.get("human_label"))==positive_label
        if pred and actual: tp+=1
        elif pred: fp+=1
        elif actual: fn+=1
        else: tn+=1
    precision=tp/(tp+fp) if tp+fp else None; recall=tp/(tp+fn) if tp+fn else None; accuracy=(tp+tn)/len(vals) if vals else None
    return {"schema_version":"geowatch-gold-holdout-eval-v1","count":len(vals),"threshold":threshold,"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":precision,"recall":recall,"accuracy":accuracy,"holdout_only":True}

from __future__ import annotations

from collections import Counter,defaultdict
from typing import Iterable

VALID_LABELS={"episode_merge_split":{"separate","merge"},"conflict_vs_context":{"conflict","context"}}


def make_review_batch(candidates: Iterable[dict], *, batch_id: str, limit: int=100) -> dict:
    rows=[]
    for row in candidates:
        if len(rows)>=limit: break
        if row.get("review_status","unreviewed")!="unreviewed": continue
        rows.append({**row,"batch_id":batch_id,"human_label":None,"reviewer":None,"reviewed_at":None})
    return {"schema_version":"geowatch-human-review-batch-v1","batch_id":batch_id,"count":len(rows),"items":rows,"labels_must_be_human_supplied":True}


def validate_reviewed_batch(batch: dict) -> dict:
    accepted=[]; rejected=[]
    for row in batch.get("items",[]):
        task=row.get("task_type"); label=row.get("human_label")
        issues=[]
        if task not in VALID_LABELS: issues.append("unsupported_task_type")
        elif label not in VALID_LABELS[task]: issues.append("invalid_or_missing_human_label")
        if not row.get("reviewer"): issues.append("missing_reviewer")
        if not row.get("reviewed_at"): issues.append("missing_reviewed_at")
        if issues: rejected.append({"candidate_id":row.get("candidate_id"),"issues":issues})
        else: accepted.append({**row,"review_status":"reviewed","human_gold":True})
    return {"schema_version":"geowatch-human-gold-validation-v1","accepted":accepted,"accepted_count":len(accepted),"rejected":rejected,"rejected_count":len(rejected),"no_automatic_gold_labels":True}


def binary_review_metrics(rows: Iterable[dict], *, task_type: str, positive_label: str) -> dict:
    vals=[r for r in rows if r.get("task_type")==task_type and r.get("human_gold") is True and r.get("machine_label") is not None]
    tp=fp=tn=fn=0
    for r in vals:
        pred=str(r.get("machine_label"))==positive_label; actual=str(r.get("human_label"))==positive_label
        if pred and actual: tp+=1
        elif pred and not actual: fp+=1
        elif not pred and actual: fn+=1
        else: tn+=1
    precision=tp/(tp+fp) if tp+fp else None; recall=tp/(tp+fn) if tp+fn else None; fpr=fp/(fp+tn) if fp+tn else None
    return {"schema_version":"geowatch-human-gold-metrics-v1","task_type":task_type,"count":len(vals),"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":round(precision,6) if precision is not None else None,"recall":round(recall,6) if recall is not None else None,"false_positive_rate":round(fpr,6) if fpr is not None else None}


def calibration_segments(rows: Iterable[dict], *, min_samples: int=30) -> dict:
    groups=defaultdict(list)
    for row in rows:
        if row.get("human_gold") is not True: continue
        region=str(row.get("region") or "unknown")
        mix="+".join(sorted(str(x) for x in (row.get("source_mix") or []))) or "unknown"
        groups[(region,mix)].append(row)
    segments=[]
    for (region,mix),vals in sorted(groups.items()):
        scores=[float(r["machine_score"]) for r in vals if isinstance(r.get("machine_score"),(int,float))]
        labels=[r for r in vals if r.get("human_label") is not None]
        eligible=len(scores)>=min_samples and len(labels)>=min_samples
        segments.append({"region":region,"source_mix":mix,"sample_count":len(vals),"eligible_for_threshold_calibration":eligible,"score_median":round(sorted(scores)[len(scores)//2],4) if scores else None})
    return {"schema_version":"geowatch-calibration-segments-v1","minimum_samples":min_samples,"segments":segments,"thresholds_not_auto_promoted":True}


def gold_progress(rows: Iterable[dict]) -> dict:
    vals=list(rows); by_task=Counter(str(r.get("task_type")) for r in vals if r.get("human_gold") is True)
    return {"schema_version":"geowatch-human-gold-progress-v1","human_gold_count":sum(by_task.values()),"by_task":dict(by_task),"target_100_reached":sum(by_task.values())>=100,"target_500_reached":sum(by_task.values())>=500}

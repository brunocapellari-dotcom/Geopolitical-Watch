from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def classification_metrics(rows: Iterable[dict]) -> dict:
    values = list(rows)
    tp = sum(1 for r in values if bool(r.get("predicted")) and bool(r.get("actual")))
    fp = sum(1 for r in values if bool(r.get("predicted")) and not bool(r.get("actual")))
    tn = sum(1 for r in values if not bool(r.get("predicted")) and not bool(r.get("actual")))
    fn = sum(1 for r in values if not bool(r.get("predicted")) and bool(r.get("actual")))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    fpr = fp / (fp + tn) if fp + tn else None
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 6) if precision is not None else None,
        "recall": round(recall, 6) if recall is not None else None,
        "false_positive_rate": round(fpr, 6) if fpr is not None else None,
        "sample_size": len(values),
    }


def evaluate_alert_labels(rows: Iterable[dict]) -> dict:
    values = list(rows)
    by_policy: dict[str, list[dict]] = defaultdict(list)
    by_region: dict[str, list[dict]] = defaultdict(list)
    for row in values:
        by_policy[str(row.get("policy_id") or "unknown")].append(row)
        by_region[str(row.get("region") or "unknown")].append(row)
    return {
        "schema_version": "geowatch-alert-evaluation-v1",
        "overall": classification_metrics(values),
        "by_policy": {key: classification_metrics(group) for key, group in sorted(by_policy.items())},
        "by_region": {key: classification_metrics(group) for key, group in sorted(by_region.items())},
        "requires_gold_labels": True,
    }

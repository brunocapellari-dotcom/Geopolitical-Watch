from __future__ import annotations

import argparse,json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.gold_calibration import deterministic_gold_split,evaluate_holdout,segmented_thresholds,threshold_scan


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--gold",default="generated/human_gold/gold_v1.json"); p.add_argument("--out",default="generated/gold_calibration"); args=p.parse_args()
    path=Path(args.gold); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        payload={"schema_version":"geowatch-gold-calibration-gate-v1","status":"blocked_no_human_gold","gold_count":0,"calibration_not_run_on_machine_labels":True}
        (out/"summary.json").write_text(json.dumps(payload,indent=2),encoding="utf-8"); print(json.dumps(payload,indent=2)); return 0
    raw=json.loads(path.read_text(encoding="utf-8")); rows=((raw.get("gold") or {}).get("items") or raw.get("human_gold") or [])
    split=deterministic_gold_split(rows,holdout_fraction=0.2)
    tasks={}
    for task,positive in (("episode_merge_split","merge"),("conflict_vs_context","conflict")):
        train=[r for r in split["train"] if r.get("task_type")==task]; hold=[r for r in split["holdout"] if r.get("task_type")==task]
        scan=threshold_scan(train,positive_label=positive); best=(scan.get("best") or {}).get("threshold")
        tasks[task]={"train_count":len(train),"holdout_count":len(hold),"scan":scan,"segments":segmented_thresholds(train,positive_label=positive,min_samples=30),"holdout":evaluate_holdout(hold,positive_label=positive,threshold=float(best)) if best is not None and hold else None}
    payload={"schema_version":"geowatch-gold-calibration-gate-v1","status":"evaluated" if rows else "blocked_no_human_gold","gold_count":len(rows),"split":{"train_count":split["train_count"],"holdout_count":split["holdout_count"]},"tasks":tasks,"thresholds_not_auto_promoted":True,"holdout_never_used_for_threshold_search":True}
    (out/"summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({"status":payload["status"],"gold_count":len(rows),"split":payload["split"]},indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())

from __future__ import annotations

import argparse,csv,json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.human_gold import validate_reviewed_batch,gold_progress,binary_review_metrics,calibration_segments


def _load(path: Path): return json.loads(path.read_text(encoding="utf-8"))


def export_batch(batch_path: Path, out_dir: Path) -> dict:
    batch=_load(batch_path); out_dir.mkdir(parents=True,exist_ok=True)
    stem=batch_path.stem
    json_out=out_dir/f"{stem}_review.json"; csv_out=out_dir/f"{stem}_review.csv"
    json_out.write_text(json.dumps(batch,ensure_ascii=False,indent=2),encoding="utf-8")
    fields=["candidate_id","task_type","case_id","region","start","end","machine_label","machine_score","human_label","reviewer","reviewed_at"]
    with csv_out.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=fields,extrasaction="ignore"); w.writeheader();
        for row in batch.get("items",[]): w.writerow(row)
    return {"batch_id":batch.get("batch_id"),"count":batch.get("count",0),"json":str(json_out),"csv":str(csv_out)}


def import_reviewed(paths: list[Path], out_path: Path) -> dict:
    accepted=[]; rejected=[]
    for path in paths:
        result=validate_reviewed_batch(_load(path)); accepted.extend(result["accepted"]); rejected.extend(result["rejected"])
    payload={"schema_version":"geowatch-human-gold-dataset-v1","human_gold":accepted,"rejected":rejected,"progress":gold_progress(accepted)}
    payload["metrics"]={
        "merge_split":binary_review_metrics(accepted,task_type="episode_merge_split",positive_label="merge"),
        "conflict_context":binary_review_metrics(accepted,task_type="conflict_vs_context",positive_label="conflict"),
    }
    payload["calibration_segments"]=calibration_segments(accepted,min_samples=30)
    out_path.parent.mkdir(parents=True,exist_ok=True); out_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return payload


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--source-dir",default="generated/ucdp"); p.add_argument("--out-dir",default="generated/human_review"); p.add_argument("--import-reviewed",nargs="*"); p.add_argument("--gold-out",default="generated/human_gold/gold_v1.json"); args=p.parse_args()
    if args.import_reviewed:
        payload=import_reviewed([Path(x) for x in args.import_reviewed],Path(args.gold_out)); print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0 if not payload["rejected"] else 2
    source=Path(args.source_dir); batches=sorted(source.glob("human_review_batch_*.json")); results=[export_batch(path,Path(args.out_dir)) for path in batches]
    print(json.dumps({"schema_version":"geowatch-human-review-export-v1","batch_count":len(results),"item_count":sum(r["count"] for r in results),"exports":results,"not_human_gold_until_reviewed":True},ensure_ascii=False,indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())

from __future__ import annotations

import argparse,csv,json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.human_review_workflow import adjudication_queue,finalize_gold,inter_rater_agreement
from geowatch.human_gold import binary_review_metrics,gold_progress


def load_csv(path: Path)->list[dict]:
    with path.open(encoding="utf-8-sig",newline="") as fh: return [dict(r) for r in csv.DictReader(fh)]


def load_json(path: Path,default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--reviews",nargs="+",required=True); p.add_argument("--adjudications"); p.add_argument("--out",default="generated/human_gold"); args=p.parse_args()
    reviews=[]
    for raw in args.reviews: reviews.extend(load_csv(Path(raw)))
    adjudications=[]
    if args.adjudications:
        path=Path(args.adjudications); adjudications=load_csv(path) if path.suffix.lower()==".csv" else load_json(path,{}).get("items",[])
    agreement=inter_rater_agreement(reviews); queue=adjudication_queue(reviews); gold=finalize_gold(reviews,adjudications)
    progress=gold_progress(gold["items"]); metrics={
        "merge_split":binary_review_metrics(gold["items"],task_type="episode_merge_split",positive_label="merge"),
        "conflict_context":binary_review_metrics(gold["items"],task_type="conflict_vs_context",positive_label="conflict"),
    }
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    (out/"adjudication_queue.json").write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding="utf-8")
    payload={"schema_version":"geowatch-human-gold-import-v2","agreement":agreement,"gold":gold,"progress":progress,"metrics":metrics,"reviews_loaded":len(reviews),"adjudications_loaded":len(adjudications),"machine_cannot_self_adjudicate":True}
    (out/"gold_v1.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in payload.items() if k!="gold"},ensure_ascii=False,indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())

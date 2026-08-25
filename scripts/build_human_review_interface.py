from __future__ import annotations

import argparse,json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.human_review_workflow import render_review_html,review_batch_csv


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--batch",default="generated/ucdp/human_review_batch_001.json"); p.add_argument("--out",default="generated/human_review/interface"); args=p.parse_args()
    batch=json.loads(Path(args.batch).read_text(encoding="utf-8")); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    (out/"batch_001.html").write_text(render_review_html(batch),encoding="utf-8")
    csv_text=review_batch_csv(batch); (out/"batch_001_reviewer_A.csv").write_text(csv_text,encoding="utf-8"); (out/"batch_001_reviewer_B.csv").write_text(csv_text,encoding="utf-8")
    summary={"schema_version":"geowatch-human-review-interface-v1","batch_id":batch.get("batch_id"),"item_count":len(batch.get("items",[])),"html":"batch_001.html","reviewer_packets":["batch_001_reviewer_A.csv","batch_001_reviewer_B.csv"],"human_labels_required":True,"reviewer_identity_and_timestamp_required":True}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0 if summary["item_count"]>=100 else 2

if __name__=="__main__": raise SystemExit(main())

from __future__ import annotations

import argparse,json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.reliability_score import reliability_dashboard


def load(path: Path,default: dict)->dict:
    if not path.exists(): return default
    return json.loads(path.read_text(encoding="utf-8"))


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--source-summary",default="reports/source_resilience.json"); p.add_argument("--slo",default="config/operations/source_slo.json"); p.add_argument("--out",default="reports/source_reliability.json"); args=p.parse_args()
    payload=reliability_dashboard(load(Path(args.source_summary),{"sources":[]}),load(Path(args.slo),{"sources":[]}))
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())

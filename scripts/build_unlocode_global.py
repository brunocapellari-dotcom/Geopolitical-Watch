from __future__ import annotations

import argparse,json
from collections import Counter
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.http import get
from geowatch.sources.unlocode import parse_unlocode_csv

DEFAULT_MIRROR="https://raw.githubusercontent.com/datasets/un-locode/main/data/code-list.csv"


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--url",default=DEFAULT_MIRROR); p.add_argument("--out",default="generated/unlocode"); args=p.parse_args()
    response=get(args.url,timeout=180,retries=3,backoff_seconds=2.0,max_backoff_seconds=20)
    rows=parse_unlocode_csv(response.payload,source_release="2025-1")
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    payload={"schema_version":"geowatch-unlocode-global-v1","canonical_source":"UNECE UN/LOCODE","source_release":"2025-1","operational_mirror_url":response.url,"mirror_is_transport_not_independent_evidence":True,"row_count":len(rows),"port_count":sum(r.get("is_port") for r in rows),"airport_count":sum(r.get("is_airport") for r in rows),"rail_terminal_count":sum(r.get("is_rail_terminal") for r in rows),"country_counts":dict(Counter(str(r.get("country_code")) for r in rows)),"rows":rows,"identity_reference_not_criticality":True}
    (out/"global_locations.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={k:v for k,v in payload.items() if k not in {"rows","country_counts"}}; summary["country_count"]=len(payload["country_counts"])
    (out/"global_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0 if len(rows)>10000 else 2

if __name__=="__main__": raise SystemExit(main())

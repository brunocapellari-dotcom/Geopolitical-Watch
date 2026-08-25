from __future__ import annotations

import argparse,json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.http import get
from geowatch.sources.unlocode import parse_unlocode_csv,port_rows

DEFAULT_MIRROR="https://raw.githubusercontent.com/datasets/un-locode/main/data/code-list.csv"


def norm(value): return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--wpi",default="generated/wpi/critical_port_candidates.json"); p.add_argument("--url",default=DEFAULT_MIRROR); p.add_argument("--out",default="generated/unlocode"); args=p.parse_args()
    response=get(args.url,timeout=180,retries=3,backoff_seconds=2.0,max_backoff_seconds=20)
    locode=port_rows(parse_unlocode_csv(response.payload,source_release="2025-1"))
    wpi=json.loads(Path(args.wpi).read_text(encoding="utf-8")); nodes=wpi.get("nodes",[])
    exact={norm(r.get("unlocode")):r for r in locode if r.get("unlocode")}
    by_name={}
    for row in locode:
        key=(norm(row.get("country_code")),norm(row.get("location_name")))
        if key[0] and key[1]: by_name.setdefault(key,[]).append(row)
    matches=[]
    for node in nodes:
        key=norm(node.get("un_locode")); match=exact.get(key) if key else None; method="exact_unlocode" if match else None
        if match is None:
            candidates=by_name.get((norm(node.get("country")),norm(node.get("name"))),[])
            if len(candidates)==1: match=candidates[0]; method="exact_country_name"
        matches.append({
            "node_id":node.get("node_id"),"wpi_name":node.get("name"),"wpi_country":node.get("country"),"wpi_unlocode":node.get("un_locode"),
            "matched":match is not None,"match_method":method,"unlocode":match.get("unlocode") if match else None,"unlocode_name":match.get("location_name") if match else None,
            "identity_corroborated":match is not None,"strategic_criticality_not_proven":True,
        })
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    payload={
        "schema_version":"geowatch-wpi-unlocode-crossmatch-v1","source_release":"2025-1","canonical_source":"UNECE UN/LOCODE",
        "operational_mirror_url":response.url,"mirror_is_transport_not_independent_evidence":True,
        "unlocode_port_rows":len(locode),"wpi_candidates":len(nodes),"matched_count":sum(r["matched"] for r in matches),
        "exact_unlocode_count":sum(r["match_method"]=="exact_unlocode" for r in matches),"exact_country_name_count":sum(r["match_method"]=="exact_country_name" for r in matches),
        "matches":matches,"identity_corroboration_not_criticality":True,
    }
    (out/"wpi_crossmatch.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in payload.items() if k!="matches"},ensure_ascii=False,indent=2)); return 0 if payload["matched_count"]>0 else 2

if __name__=="__main__": raise SystemExit(main())

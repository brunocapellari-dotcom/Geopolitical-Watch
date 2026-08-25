from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()


def norm(value): return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def main()->int:
    wpi=json.loads(Path("generated/wpi/all_ports.json").read_text(encoding="utf-8")); loc=json.loads(Path("generated/unlocode/global_locations.json").read_text(encoding="utf-8"))
    loc_rows=[r for r in loc.get("rows",[]) if r.get("is_port")]
    exact={norm(r.get("unlocode")):r for r in loc_rows if r.get("unlocode")}
    by_name={}
    for row in loc_rows:
        key=(norm(row.get("country_code")),norm(row.get("location_name")))
        if key[0] and key[1]: by_name.setdefault(key,[]).append(row)
    matches=[]
    for node in wpi.get("nodes",[]):
        match=None; method=None; code=norm(node.get("un_locode"))
        if code and code in exact: match=exact[code]; method="exact_unlocode"
        if match is None:
            rows=by_name.get((norm(node.get("country")),norm(node.get("name"))),[])
            if len(rows)==1: match=rows[0]; method="exact_country_name"
        matches.append({"node_id":node.get("node_id"),"wpi_name":node.get("name"),"country":node.get("country"),"wpi_unlocode":node.get("un_locode"),"unlocode":match.get("unlocode") if match else None,"unlocode_name":match.get("location_name") if match else None,"match_method":method,"matched":match is not None,"identity_corroborated":match is not None,"strategic_criticality_not_proven":True})
    out=Path("generated/unlocode"); out.mkdir(parents=True,exist_ok=True)
    payload={"schema_version":"geowatch-global-port-crosswalk-v1","wpi_port_count":len(wpi.get("nodes",[])),"unlocode_port_count":len(loc_rows),"matched_count":sum(r["matched"] for r in matches),"unmatched_count":sum(not r["matched"] for r in matches),"match_methods":dict(Counter(str(r.get("match_method") or "unmatched") for r in matches)),"matches":matches,"identity_corroboration_not_criticality":True}
    (out/"global_wpi_crosswalk.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={k:v for k,v in payload.items() if k!="matches"}; (out/"global_wpi_crosswalk_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0 if payload["matched_count"]>1000 else 2

if __name__=="__main__": raise SystemExit(main())

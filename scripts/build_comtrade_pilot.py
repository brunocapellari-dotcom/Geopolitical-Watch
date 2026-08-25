from __future__ import annotations

import argparse,json
from datetime import datetime,timezone
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.sources.un_comtrade import query_trade,normalize_trade_records,attach_domains
from geowatch.strategic_flows import dependency_metrics

REPORTERS={"China":156,"India":356,"Japan":392,"South Korea":410,"United States":842}
DOMAINS={"energy":"27","fertilizer":"31","food":"10,12","critical_mineral":"26,28,71,74,75,76,79,81","general_trade":"TOTAL"}


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--period",default="2025"); p.add_argument("--out",default="generated/comtrade"); args=p.parse_args()
    collected=datetime.now(timezone.utc).isoformat(); observations=[]; calls=[]
    for reporter_name,code in REPORTERS.items():
        for domain,cmd in DOMAINS.items():
            try:
                response=query_trade(reporter_code=code,partner_code=0,period=args.period,cmd_code=cmd,flow_code="M",frequency="A")
                rows=attach_domains(normalize_trade_records(response["payload"],collected_at=collected))
                for row in rows:
                    if domain!="general_trade": row["domain"]=domain
                observations.extend(rows)
                calls.append({"reporter":reporter_name,"domain":domain,"status":"ok","records":len(rows),"auth_mode":response["auth_mode"]})
            except Exception as exc:
                calls.append({"reporter":reporter_name,"domain":domain,"status":"error","error":f"{type(exc).__name__}: {exc}"})
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    payload={
        "schema_version":"geowatch-comtrade-strategic-pilot-v1","period":args.period,"collected_at":collected,"calls":calls,"observations":observations,
        "reporter_count":len(REPORTERS),"domain_count":len(DOMAINS),"successful_calls":sum(r["status"]=="ok" for r in calls),"failed_calls":sum(r["status"]!="ok" for r in calls),
        "pilot_is_partial_not_global_matrix":True,"public_preview_caps_and_reporting_lags_apply":True,
    }
    (out/"pilot.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={k:v for k,v in payload.items() if k!="observations"}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0 if payload["successful_calls"]>=len(REPORTERS) else 2

if __name__=="__main__": raise SystemExit(main())

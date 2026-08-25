from __future__ import annotations

import argparse,json,os
from datetime import datetime,timezone
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.sources.un_comtrade import query_trade,normalize_trade_records,attach_domains

DEFAULT_REPORTERS={"China":156,"India":356,"Japan":392,"South Korea":410,"United States":842,"Brazil":76,"European Union":97}
DEFAULT_DOMAINS={"energy":"27","fertilizer":"31","food_cereals":"10","food_oilseeds":"12","critical_mineral_ores":"26","critical_mineral_metals":"81"}


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--period",default="2025"); p.add_argument("--out",default="generated/comtrade_matrix"); p.add_argument("--allow-preview",action="store_true"); args=p.parse_args()
    key=os.getenv("UN_COMTRADE_KEY"); out=Path(args.out); out.mkdir(parents=True,exist_ok=True); collected=datetime.now(timezone.utc).isoformat()
    if not key and not args.allow_preview:
        payload={"schema_version":"geowatch-comtrade-matrix-v1","status":"credential_blocked","required_secret":"UN_COMTRADE_KEY","preview_available":True,"complete_matrix_not_claimed":True}
        (out/"summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(payload,indent=2)); return 0
    observations=[]; calls=[]
    max_records=250000 if key else 500
    for reporter_name,reporter_code in DEFAULT_REPORTERS.items():
        for domain,cmd in DEFAULT_DOMAINS.items():
            try:
                response=query_trade(reporter_code=reporter_code,partner_code=None,period=args.period,cmd_code=cmd,flow_code="M",frequency="A",subscription_key=key,max_records=max_records)
                rows=attach_domains(normalize_trade_records(response["payload"],collected_at=collected))
                for row in rows: row["domain"]=domain; row["reporter_requested"]=reporter_name
                observations.extend(rows)
                calls.append({"reporter":reporter_name,"domain":domain,"status":"ok","records":len(rows),"auth_mode":response["auth_mode"],"possibly_censored":response["auth_mode"]=="public_preview" and len(rows)>=500})
            except Exception as exc:
                calls.append({"reporter":reporter_name,"domain":domain,"status":"error","error":f"{type(exc).__name__}: {exc}"})
    payload={"schema_version":"geowatch-comtrade-matrix-v1","status":"complete_run" if key else "preview_run","period":args.period,"collected_at":collected,"subscription_key_used":bool(key),"call_count":len(calls),"successful_calls":sum(r["status"]=="ok" for r in calls),"possibly_censored_calls":sum(bool(r.get("possibly_censored")) for r in calls),"observations":observations,"calls":calls,"complete_matrix_claim_allowed":bool(key) and all(r["status"]=="ok" for r in calls) and not any(r.get("possibly_censored") for r in calls),"reporting_lags_apply":True}
    (out/"matrix.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={k:v for k,v in payload.items() if k!="observations"}; summary["observation_count"]=len(observations); (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0 if payload["successful_calls"]>0 else 2

if __name__=="__main__": raise SystemExit(main())

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
    p=argparse.ArgumentParser(); p.add_argument("--period",default="2025"); p.add_argument("--out",default="generated/comtrade"); p.add_argument("--smoke",action="store_true"); args=p.parse_args()
    collected=datetime.now(timezone.utc).isoformat(); observations=[]; calls=[]; dependencies=[]
    reporters=dict(list(REPORTERS.items())[:2]) if args.smoke else REPORTERS
    domains={"energy":"27","fertilizer":"31"} if args.smoke else DOMAINS
    for reporter_name,code in reporters.items():
        for domain,cmd in domains.items():
            try:
                response=query_trade(reporter_code=code,partner_code=None,period=args.period,cmd_code=cmd,flow_code="M",frequency="A",max_records=500)
                rows=attach_domains(normalize_trade_records(response["payload"],collected_at=collected))
                for row in rows:
                    if domain!="general_trade": row["domain"]=domain
                observations.extend(rows)
                capped=response["auth_mode"]=="public_preview" and len(rows)>=500
                calls.append({"reporter":reporter_name,"domain":domain,"status":"ok","records":len(rows),"auth_mode":response["auth_mode"],"possibly_censored_by_preview_cap":capped})
                metric=dependency_metrics(rows,reporter=reporter_name,domain=domain,flow="imports")
                if metric.get("periods"): dependencies.append(metric)
            except Exception as exc:
                calls.append({"reporter":reporter_name,"domain":domain,"status":"error","error":f"{type(exc).__name__}: {exc}"})
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    payload={
        "schema_version":"geowatch-comtrade-strategic-pilot-v2","period":args.period,"collected_at":collected,"calls":calls,"observations":observations,"dependencies":dependencies,
        "reporter_count":len(reporters),"domain_count":len(domains),"successful_calls":sum(r["status"]=="ok" for r in calls),"failed_calls":sum(r["status"]!="ok" for r in calls),
        "possibly_censored_calls":sum(bool(r.get("possibly_censored_by_preview_cap")) for r in calls),
        "pilot_is_partial_not_global_matrix":True,"public_preview_caps_and_reporting_lags_apply":True,
        "partner_distributions_requested":True,"censored_preview_results_must_not_be_treated_as_complete_partner_matrix":True
    }
    (out/"pilot.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={k:v for k,v in payload.items() if k not in {"observations","dependencies"}}
    summary["dependency_views"]=len(dependencies)
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0 if payload["successful_calls"]>=len(reporters) else 2

if __name__=="__main__": raise SystemExit(main())

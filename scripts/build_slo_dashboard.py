from __future__ import annotations

import argparse,json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.slo_analytics import burn_rate
from geowatch.slo_dashboard import build_slo_dashboard,render_slo_dashboard_html
from geowatch.source_resilience import summarize_source_history


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--history",default="state/beta/source_history.json"); p.add_argument("--slo",default="config/operations/source_slo.json"); p.add_argument("--out",default="reports"); args=p.parse_args()
    history=load(Path(args.history),{"observations":[]}); slo=load(Path(args.slo),{"sources":[]})
    summary=summarize_source_history(history,slo_config=slo)
    dashboard=build_slo_dashboard(summary,slo); targets={r.get("source_id"):r for r in slo.get("sources",[])}
    burns=[]
    for row in dashboard.get("sources",[]):
        sid=row.get("source_id"); target=float(targets.get(sid,{}).get("monthly_availability_target",0.95))
        burns.append(burn_rate(history.get("observations",[]),source_id=sid,availability_target=target,as_of=summary["as_of"]))
    dashboard["burn_rates"]=burns
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    (out/"slo_dashboard.json").write_text(json.dumps(dashboard,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"slo_dashboard.html").write_text(render_slo_dashboard_html(dashboard),encoding="utf-8")
    print(json.dumps({"schema_version":dashboard["schema_version"],"source_count":len(dashboard.get("sources",[])),"stale_alert_count":len(dashboard.get("stale_alerts",[])),"burn_rate_count":len(burns)},ensure_ascii=False,indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())

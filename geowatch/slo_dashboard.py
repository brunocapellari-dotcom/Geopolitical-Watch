from __future__ import annotations

import html
import json

from .slo_analytics import error_budget,reliability_score,stale_coverage_alerts


def build_slo_dashboard(source_summary: dict, slo_config: dict) -> dict:
    cfg={r.get("source_id"):r for r in slo_config.get("sources",[])}; rows=[]
    for row in source_summary.get("sources",[]):
        sid=row.get("source_id"); target=float(cfg.get(sid,{}).get("monthly_availability_target",0.95)); rolling=row.get("rolling_availability") or {}
        avail30=(rolling.get("30") or {}).get("availability_ratio")
        budget=error_budget(availability_target=target,observed_availability=avail30)
        reliability=reliability_score(availability_30d=avail30,freshness_slo_passed=row.get("freshness_slo_passed"),open_incident=bool(row.get("open_incident")))
        rows.append({"source_id":sid,"availability_7d":(rolling.get("7") or {}).get("availability_ratio"),"availability_30d":avail30,"availability_90d":(rolling.get("90") or {}).get("availability_ratio"),"freshness_hours":row.get("freshness_hours"),"freshness_slo_passed":row.get("freshness_slo_passed"),"mttr_minutes":row.get("mttr_minutes"),"open_incident":row.get("open_incident"),"error_budget":budget,"reliability":reliability})
    return {"schema_version":"geowatch-slo-dashboard-v1","as_of":source_summary.get("as_of"),"sources":rows,"stale_alerts":stale_coverage_alerts(source_summary,slo_config),"operational_metrics_not_intelligence_accuracy":True}


def render_slo_dashboard_html(payload: dict) -> str:
    rows=[]
    for r in payload.get("sources",[]):
        def pct(v): return "—" if v is None else f"{100*float(v):.2f}%"
        rel=r.get("reliability") or {}; budget=r.get("error_budget") or {}
        rows.append("<tr>"+"".join([
            f"<td>{html.escape(str(r.get('source_id')))}</td>",f"<td>{pct(r.get('availability_7d'))}</td>",f"<td>{pct(r.get('availability_30d'))}</td>",f"<td>{pct(r.get('availability_90d'))}</td>",f"<td>{html.escape(str(r.get('freshness_hours') if r.get('freshness_hours') is not None else '—'))}</td>",f"<td>{html.escape(str(r.get('mttr_minutes') if r.get('mttr_minutes') is not None else '—'))}</td>",f"<td>{html.escape(str(rel.get('score') if rel.get('score') is not None else '—'))}</td>",f"<td>{html.escape(str(budget.get('budget_remaining_ratio') if budget.get('budget_remaining_ratio') is not None else '—'))}</td>" ])+"</tr>")
    data=json.dumps(payload,ensure_ascii=False)
    return f"""<!doctype html><meta charset='utf-8'><title>Geowatch SLO Dashboard</title><style>body{{font-family:system-ui;margin:24px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:8px;text-align:right}}th:first-child,td:first-child{{text-align:left}}.note{{color:#555}}</style><h1>Geowatch Source SLO Dashboard</h1><p class='note'>Operational availability and freshness only. These metrics are not intelligence accuracy.</p><table><thead><tr><th>Source</th><th>7d</th><th>30d</th><th>90d</th><th>Freshness h</th><th>MTTR min</th><th>Reliability</th><th>Error budget left</th></tr></thead><tbody>{''.join(rows)}</tbody></table><script type='application/json' id='payload'>{html.escape(data)}</script>"""

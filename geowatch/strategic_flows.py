from __future__ import annotations

from collections import defaultdict
from typing import Iterable

DOMAINS={"energy","food","fertilizer","critical_mineral","general_trade"}


def normalize_flow(row: dict) -> dict:
    value=row.get("value")
    return {
        "source_id":row.get("source_id"),"reference_period":row.get("reference_period"),"collected_at":row.get("collected_at"),
        "reporter":row.get("reporter") or row.get("origin"),"partner":row.get("partner") or row.get("destination"),
        "flow":row.get("flow"),"domain":row.get("domain") if row.get("domain") in DOMAINS else "general_trade",
        "commodity_code":row.get("commodity_code"),"commodity_name":row.get("commodity_name"),
        "value":float(value) if isinstance(value,(int,float)) else None,"unit":row.get("unit"),
        "observed":value is not None,"missing_is_unknown_not_zero":True,
    }


def dependency_metrics(rows: Iterable[dict], *, reporter: str, domain: str, flow: str="imports") -> dict:
    vals=[normalize_flow(r) for r in rows]
    vals=[r for r in vals if r["reporter"]==reporter and r["domain"]==domain and str(r.get("flow") or "").casefold()==flow.casefold() and r["value"] is not None and r["value"]>=0]
    periods=defaultdict(list)
    for r in vals: periods[str(r.get("reference_period") or "unknown")].append(r)
    out=[]
    for period,group in sorted(periods.items()):
        total=sum(r["value"] for r in group)
        partner_totals=defaultdict(float)
        for r in group: partner_totals[str(r.get("partner") or "unknown")]+=r["value"]
        shares=sorted(((p,v/total if total else 0.0) for p,v in partner_totals.items()),key=lambda x:x[1],reverse=True)
        hhi=sum(s*s for _,s in shares)
        out.append({
            "reference_period":period,"total_value":total,"unit":next((r.get("unit") for r in group if r.get("unit")),None),
            "partner_count":len(shares),"top_partners":[{"partner":p,"share":round(s,6)} for p,s in shares[:10]],
            "hhi":round(hhi,6),"top1_share":round(shares[0][1],6) if shares else None,"top3_share":round(sum(s for _,s in shares[:3]),6) if shares else None,
        })
    return {"schema_version":"geowatch-strategic-dependency-v1","reporter":reporter,"domain":domain,"flow":flow,"periods":out,"concentration_is_exposure_not_predicted_loss":True}


def source_freshness(rows: Iterable[dict]) -> dict:
    vals=[normalize_flow(r) for r in rows]; by_source=defaultdict(list)
    for r in vals: by_source[str(r.get("source_id"))].append(r)
    return {"schema_version":"geowatch-strategic-flow-freshness-v1","sources":[{"source_id":sid,"latest_reference_period":max((str(r.get("reference_period")) for r in group if r.get("reference_period")),default=None),"observations":sum(r["observed"] for r in group),"missing":sum(not r["observed"] for r in group)} for sid,group in sorted(by_source.items())]}

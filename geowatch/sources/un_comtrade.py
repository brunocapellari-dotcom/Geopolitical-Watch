from __future__ import annotations

import os
from typing import Iterable

from ..http import get,json_body

BASE="https://comtradeapi.un.org"


def query_trade(*, reporter_code: int, partner_code: int=0, period: str, cmd_code: str="TOTAL", flow_code: str="X", frequency: str="A", subscription_key: str | None=None, max_records: int=500) -> dict:
    key=subscription_key or os.getenv("UN_COMTRADE_KEY")
    if key:
        url=f"{BASE}/data/v1/get/C/{frequency}/HS"
        headers={"Ocp-Apim-Subscription-Key":key}
        query={"reporterCode":reporter_code,"partnerCode":partner_code,"period":period,"cmdCode":cmd_code,"flowCode":flow_code,"maxrecords":min(int(max_records),250000)}
        auth_mode="subscription"
    else:
        url=f"{BASE}/public/v1/preview/C/{frequency}/HS"
        headers={}
        query={"reporterCode":reporter_code,"partnerCode":partner_code,"period":period,"cmdCode":cmd_code,"flowCode":flow_code}
        auth_mode="public_preview"
    payload=json_body(get(url,headers=headers,query=query,retries=3,backoff_seconds=2.0))
    return {"schema_version":"geowatch-un-comtrade-response-v1","auth_mode":auth_mode,"payload":payload,"preview_record_cap_applies":auth_mode=="public_preview"}


def normalize_trade_records(payload: dict, *, collected_at: str) -> list[dict]:
    data=payload.get("data") or payload.get("dataset") or []
    rows=[]
    for r in data:
        value=r.get("primaryValue") if r.get("primaryValue") is not None else r.get("TradeValue")
        rows.append({
            "source_id":"un_comtrade","reference_period":str(r.get("period") or r.get("refYear") or ""),"collected_at":collected_at,
            "reporter":r.get("reporterDesc") or r.get("reporterCode"),"partner":r.get("partnerDesc") or r.get("partnerCode"),
            "flow":"imports" if str(r.get("flowCode"))=="M" else "exports" if str(r.get("flowCode"))=="X" else r.get("flowDesc"),
            "commodity_code":r.get("cmdCode"),"commodity_name":r.get("cmdDesc"),"value":value,"unit":"USD",
            "domain":"general_trade","provider_row":r,"reported_trade_data":True,
        })
    return rows


def commodity_domain(hs_code: str | None) -> str:
    code=str(hs_code or "")
    if code.startswith(("27",)): return "energy"
    if code.startswith(("01","02","03","04","07","08","09","10","11","12","15","16","17","18","19","20","21","22","23","24")): return "food"
    if code.startswith(("31",)): return "fertilizer"
    if code.startswith(("25","26","28","71","72","74","75","76","78","79","80","81")): return "critical_mineral"
    return "general_trade"


def attach_domains(rows: Iterable[dict]) -> list[dict]:
    return [{**r,"domain":commodity_domain(r.get("commodity_code"))} for r in rows]

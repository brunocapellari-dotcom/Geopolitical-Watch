from __future__ import annotations

import csv
import io
import re
from typing import Iterable

from ..http import get

CATALOG_BASE="https://data.fao.org/catalog/dataset"


def fetch_catalog_page(dataset_id: str, *, timeout: int=60) -> tuple[bytes,str]:
    response=get(f"{CATALOG_BASE}/{dataset_id}",timeout=timeout,retries=3,backoff_seconds=2.0)
    return response.payload,response.url


def discover_smart_csv_urls(payload: bytes) -> list[str]:
    text=payload.decode("utf-8",errors="replace")
    candidates=re.findall(r'https://api\.data\.apps\.fao\.org/api/v2/bigquery\?[^"\'<> ]+',text)
    decoded=[]
    for url in candidates:
        url=url.replace("&amp;","&")
        if url not in decoded: decoded.append(url)
    return decoded


def parse_csv(payload: bytes, *, dataset_id: str, collected_at: str) -> list[dict]:
    text=payload.decode("utf-8-sig",errors="replace"); reader=csv.DictReader(io.StringIO(text)); out=[]
    for raw in reader:
        norm={str(k or "").strip().casefold().replace(" ","_"):v for k,v in raw.items()}
        value=norm.get("value") or norm.get("value_numeric") or norm.get("obs_value")
        try: numeric=float(str(value).replace(",","")) if value not in (None,"") else None
        except ValueError: numeric=None
        flag=norm.get("flag") or norm.get("flag_code") or norm.get("status")
        out.append({
            "source_id":"faostat","dataset_id":dataset_id,"collected_at":collected_at,
            "area":norm.get("area") or norm.get("area_name") or norm.get("geo_area_name_m49"),"area_code":norm.get("area_code") or norm.get("m49_code"),
            "item":norm.get("item") or norm.get("item_name"),"item_code":norm.get("item_code"),"element":norm.get("element") or norm.get("element_name"),
            "year":norm.get("year") or norm.get("year_code"),"unit":norm.get("unit"),"value":numeric,"flag":flag,"raw":raw,
            "quality_flag_preserved":True,"estimated_or_imputed_must_follow_fao_flag_semantics":True,
        })
    return out


def strategic_rows(rows: Iterable[dict], *, items: set[str]|None=None, elements: set[str]|None=None) -> list[dict]:
    item_keys={x.casefold() for x in (items or set())}; element_keys={x.casefold() for x in (elements or set())}; out=[]
    for r in rows:
        if item_keys and str(r.get("item") or "").casefold() not in item_keys: continue
        if element_keys and str(r.get("element") or "").casefold() not in element_keys: continue
        out.append(dict(r))
    return out


def catalog_smoke(dataset_id: str) -> dict:
    payload,url=fetch_catalog_page(dataset_id); smart=discover_smart_csv_urls(payload)
    return {"schema_version":"geowatch-faostat-catalog-smoke-v1","dataset_id":dataset_id,"catalog_url":url,"bytes":len(payload),"smart_csv_urls":smart,"smart_csv_discovered":bool(smart),"catalog_access_is_not_data_ingestion":True}

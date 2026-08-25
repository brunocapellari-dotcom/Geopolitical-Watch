from __future__ import annotations

import csv
import io
import json
from typing import Iterable

from ..http import get,json_body

SCIENCEBASE_ITEM_ID="69837e43b66b01367d7ec7c7"
SCIENCEBASE_URL=f"https://www.sciencebase.gov/catalog/item/{SCIENCEBASE_ITEM_ID}?format=json"


def fetch_release_metadata(*, timeout: int=60) -> dict:
    response=get(SCIENCEBASE_URL,timeout=timeout,retries=3,backoff_seconds=2.0)
    try: payload=json.loads(response.payload.decode("utf-8"))
    except json.JSONDecodeError: payload={"raw_text":response.payload.decode("utf-8",errors="replace")}
    return {"schema_version":"geowatch-usgs-mcs-metadata-v1","source_id":"usgs_mcs_2026","sciencebase_item_id":SCIENCEBASE_ITEM_ID,"url":response.url,"payload":payload,"reference_years":[2021,2022,2023,2024,2025],"public_domain_data_release":True}


def file_inventory(metadata: dict) -> list[dict]:
    payload=metadata.get("payload") or {}; files=[]
    for row in payload.get("files") or []:
        files.append({"name":row.get("name"),"url":row.get("url"),"content_type":row.get("contentType") or row.get("content_type"),"size":row.get("size"),"date_uploaded":row.get("dateUploaded")})
    return files


def parse_csv(payload: bytes, *, file_name: str, collected_at: str) -> list[dict]:
    text=payload.decode("utf-8-sig",errors="replace"); reader=csv.DictReader(io.StringIO(text)); out=[]
    for raw in reader:
        norm={str(k or "").strip().casefold().replace(" ","_"):v for k,v in raw.items()}
        commodity=norm.get("commodity") or norm.get("mineral") or norm.get("material") or norm.get("commodity_name")
        country=norm.get("country") or norm.get("country_name")
        year=norm.get("year") or norm.get("data_year")
        value=norm.get("value") or norm.get("production") or norm.get("reserve") or norm.get("reserves")
        try: numeric=float(str(value).replace(",","")) if value not in (None,"") else None
        except ValueError: numeric=None
        out.append({"source_id":"usgs_mcs_2026","file_name":file_name,"collected_at":collected_at,"commodity":commodity,"country":country,"year":year,"value":numeric,"unit":norm.get("unit"),"measure":norm.get("measure") or norm.get("variable") or norm.get("series"),"raw":raw,"reference_period_must_be_preserved":True})
    return out


def critical_mineral_rows(rows: Iterable[dict], critical_names: Iterable[str]) -> list[dict]:
    keys={str(x).casefold() for x in critical_names}; return [dict(r) for r in rows if str(r.get("commodity") or "").casefold() in keys]

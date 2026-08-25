from __future__ import annotations

import json
import os
from typing import Iterable

from ..http import get,json_body

MANIFEST_URL="https://api.eia.gov/bulk/manifest.txt"
API_BASE="https://api.eia.gov/v2"


def fetch_bulk_manifest() -> dict:
    response=get(MANIFEST_URL,timeout=60,retries=3,backoff_seconds=2.0)
    return json.loads(response.payload.decode("utf-8"))


def international_bulk_entries(manifest: dict) -> list[dict]:
    rows=[]
    values=manifest.values() if isinstance(manifest,dict) else manifest
    for row in values:
        if not isinstance(row,dict): continue
        text=" ".join(str(row.get(k) or "") for k in ("identifier","data_set","title")).casefold()
        if "international" in text: rows.append(dict(row))
    return rows


def api_query(route: str, *, query: dict[str,str|int]|None=None, api_key: str|None=None) -> dict:
    key=api_key or os.getenv("EIA_API_KEY")
    if not key: raise RuntimeError("EIA_API_KEY is required for API v2 queries; public bulk manifest may still be used")
    path=route.strip("/"); params={"api_key":key}; params.update(query or {})
    response=get(f"{API_BASE}/{path}",query=params,timeout=90,retries=3,backoff_seconds=2.0)
    return json_body(response)


def normalize_api_rows(payload: dict, *, collected_at: str, domain: str="energy") -> list[dict]:
    data=((payload.get("response") or {}).get("data") or []); out=[]
    for row in data:
        value=row.get("value")
        try: numeric=float(value) if value not in (None,"") else None
        except (TypeError,ValueError): numeric=None
        out.append({"source_id":"eia_international","collected_at":collected_at,"reference_period":row.get("period"),"country":row.get("countryName") or row.get("countryRegionName") or row.get("countryRegionId"),"series":row.get("productName") or row.get("activityName") or row.get("seriesDescription"),"value":numeric,"unit":row.get("unitName") or row.get("unit"),"domain":domain,"raw":row,"api_values_returned_as_strings_are_normalized":True})
    return out


def activation_status() -> dict:
    return {"schema_version":"geowatch-eia-activation-v1","api_key_present":bool(os.getenv("EIA_API_KEY")),"api_v2_requires_key":True,"public_bulk_manifest_available_without_key":True,"one_missing_credential_does_not_block_other_sources":True}

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class MaritimeWarning:
    warning_id: str
    authority: str
    navarea: str | None
    reference: str | None
    issued_at: str | None
    valid_from: str | None
    valid_to: str | None
    title: str
    body: str
    latitude: float | None
    longitude: float | None
    source_url: str | None
    collected_at: str
    warning_scope_only: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_warning(item: dict, *, authority: str, collected_at: str, source_url: str | None = None) -> MaritimeWarning:
    ref=str(item.get("reference") or item.get("number") or item.get("id") or "") or None
    title=str(item.get("title") or item.get("subject") or item.get("headline") or "Navigational warning")
    body=str(item.get("body") or item.get("text") or item.get("description") or "")
    navarea=str(item.get("navarea") or item.get("area") or "") or None
    lat=_float(item.get("latitude")); lon=_float(item.get("longitude"))
    wid="nav_"+hashlib.sha256(f"{authority}|{navarea}|{ref}|{title}".encode()).hexdigest()[:20]
    return MaritimeWarning(wid,authority,navarea,ref,_str(item.get("issued_at") or item.get("issued")),_str(item.get("valid_from")),_str(item.get("valid_to")),title,body,lat,lon,source_url,collected_at)


def parse_json_feed(payload: bytes, *, authority: str, collected_at: str, source_url: str | None = None) -> list[MaritimeWarning]:
    data=json.loads(payload)
    rows=data if isinstance(data,list) else data.get("warnings") or data.get("data") or data.get("items") or []
    return [normalize_warning(row,authority=authority,collected_at=collected_at,source_url=source_url) for row in rows if isinstance(row,dict)]


def parse_text_bulletins(text: str, *, authority: str, collected_at: str, source_url: str | None = None) -> list[MaritimeWarning]:
    blocks=[block.strip() for block in re.split(r"\n\s*\n",text) if block.strip()]
    result=[]
    for block in blocks:
        lines=block.splitlines(); head=lines[0][:180]
        ref_match=re.search(r"\b(?:NAVAREA\s+)?([IVXLCDM]+)?\s*(\d{1,4}/\d{2,4})\b",head,re.I)
        nav_match=re.search(r"NAVAREA\s+([IVXLCDM]+)",block,re.I)
        item={"reference":ref_match.group(2) if ref_match else None,"navarea":nav_match.group(1).upper() if nav_match else None,"title":head,"body":block}
        result.append(normalize_warning(item,authority=authority,collected_at=collected_at,source_url=source_url))
    return result


def active_warnings(rows: Iterable[MaritimeWarning], *, at_iso: str) -> list[dict]:
    result=[]
    for row in rows:
        if row.valid_from and row.valid_from > at_iso: continue
        if row.valid_to and row.valid_to < at_iso: continue
        result.append(row.to_dict())
    return result


def _float(value):
    try: return float(value) if value not in (None,"") else None
    except (TypeError,ValueError): return None


def _str(value):
    return str(value) if value not in (None,"") else None

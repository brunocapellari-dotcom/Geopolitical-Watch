from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class SanctionsDesignation:
    designation_id: str
    authority: str
    list_name: str
    external_reference: str | None
    name: str
    entity_type: str
    programs: tuple[str, ...]
    effective_date: str | None
    source_url: str | None
    collected_at: str
    evidence_class: str = "observed"

    def to_dict(self) -> dict:
        row=asdict(self); row["programs"]=list(self.programs); return row


def parse_un_consolidated_xml(payload: bytes, *, collected_at: str, source_url: str | None = None) -> list[SanctionsDesignation]:
    root=ET.fromstring(payload)
    rows=[]
    for element in root.iter():
        tag=element.tag.rsplit("}",1)[-1].casefold()
        if tag not in {"individual","entity"}:
            continue
        values={child.tag.rsplit("}",1)[-1].casefold(): (child.text or "").strip() for child in list(element)}
        name=" ".join(filter(None,[values.get("first_name"),values.get("second_name"),values.get("third_name"),values.get("fourth_name"),values.get("name")])).strip()
        ref=values.get("reference_number") or values.get("dataid") or values.get("un_list_type")
        if not name: continue
        did="sanc_"+hashlib.sha256(f"UN|{ref}|{name}".encode()).hexdigest()[:20]
        rows.append(SanctionsDesignation(did,"UNSC","UN Consolidated List",ref,name,"individual" if tag=="individual" else "entity",tuple(filter(None,[values.get("un_list_type")])),values.get("listed_on"),source_url,collected_at))
    return rows


def parse_ofac_json(payload: bytes, *, collected_at: str, source_url: str | None = None) -> list[SanctionsDesignation]:
    data=json.loads(payload)
    candidates=data if isinstance(data,list) else data.get("data") or data.get("records") or data.get("entries") or []
    rows=[]
    for item in candidates:
        if not isinstance(item,dict): continue
        name=str(item.get("name") or item.get("caption") or item.get("fullName") or "").strip()
        if not name: continue
        ref=str(item.get("id") or item.get("uid") or item.get("sdnId") or "") or None
        programs=item.get("programs") or item.get("program") or []
        if isinstance(programs,str): programs=[programs]
        did="sanc_"+hashlib.sha256(f"OFAC|{ref}|{name}".encode()).hexdigest()[:20]
        rows.append(SanctionsDesignation(did,"US-OFAC",str(item.get("list") or "OFAC Sanctions List"),ref,name,str(item.get("type") or "unknown"),tuple(str(x) for x in programs),str(item.get("effective_date") or item.get("date") or "") or None,source_url,collected_at))
    return rows


def parse_uk_csv(payload: bytes, *, collected_at: str, source_url: str | None = None) -> list[SanctionsDesignation]:
    """Parse the current UK Sanctions List CSV defensively.

    FCDO documents wide-format headings including ``Unique ID``, ``Name 1`` …
    ``Name 6``, ``Regime Name`` and ``Individual, Entity, Ship``. The downloadable
    file may include a short preamble and its delimiter should not be assumed, so
    the parser locates the real heading row and sniffs common CSV delimiters.
    Each CSV name row is retained with the UK Unique ID; consumers can group rows
    by that ID when they need designation-level rather than name-level counts.
    """
    text = payload.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header_index = _uk_header_index(lines)
    if header_index is None:
        return []
    table = "\n".join(lines[header_index:])
    sample = table[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(table), dialect=dialect)
    rows=[]
    for item in reader:
        if not isinstance(item, dict):
            continue
        normalized={_header_key(k): str(v or "").strip() for k,v in item.items() if k is not None}
        ref=(normalized.get("unique_id") or normalized.get("uk_sanctions_list_ref") or normalized.get("group_id") or "").strip() or None
        parts=[normalized.get(f"name_{idx}", "") for idx in range(1,7)]
        # UKSL documents Name 6 as entity/ship full name or individual surname.
        name=" ".join(part for part in parts if part).strip()
        if not name:
            name=(normalized.get("name") or normalized.get("primary_name") or "").strip()
        if not name:
            continue
        regime=(normalized.get("regime_name") or normalized.get("regime") or normalized.get("sanctions_regime") or "").strip()
        entity_type=(
            normalized.get("individual_entity_ship")
            or normalized.get("designation_type")
            or normalized.get("group_type")
            or normalized.get("type")
            or "unknown"
        ).strip()
        listed=(
            normalized.get("date_designated")
            or normalized.get("date_designated_specified")
            or normalized.get("last_updated")
            or None
        )
        name_type=(normalized.get("name_type") or "").strip()
        identity_seed=f"UK|{ref}|{name}|{name_type}|{regime}"
        did="sanc_"+hashlib.sha256(identity_seed.encode()).hexdigest()[:20]
        programs=tuple(value for value in [regime] if value)
        rows.append(SanctionsDesignation(did,"UK-FCDO","UK Sanctions List",ref,name,entity_type,programs,listed,source_url,collected_at))
    return rows


def uk_csv_diagnostics(payload: bytes) -> dict:
    """Return non-sensitive structural diagnostics for schema monitoring."""
    text=payload.decode("utf-8-sig", errors="replace")
    lines=text.splitlines()
    header_index=_uk_header_index(lines)
    if header_index is None:
        return {"header_found":False,"line_count":len(lines)}
    table="\n".join(lines[header_index:])
    try:
        dialect=csv.Sniffer().sniff(table[:20000], delimiters=",;\t|")
        delimiter=dialect.delimiter
    except csv.Error:
        dialect=csv.excel; delimiter=","
    reader=csv.DictReader(io.StringIO(table),dialect=dialect)
    fieldnames=[str(value or "").strip() for value in (reader.fieldnames or [])]
    return {
        "header_found":True,
        "header_line_index":header_index,
        "delimiter":delimiter,
        "field_count":len(fieldnames),
        "fieldnames":fieldnames,
        "line_count":len(lines),
    }


def _uk_header_index(lines: list[str]) -> int | None:
    for index,line in enumerate(lines[:50]):
        folded=line.casefold()
        if "unique id" in folded and ("regime name" in folded or "name 6" in folded or "name 1" in folded):
            return index
    return None


def _header_key(value: object) -> str:
    text=str(value or "").strip().casefold()
    text=text.replace("(/ies)", "ies")
    text=re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def diff_designations(previous: Iterable[SanctionsDesignation], current: Iterable[SanctionsDesignation]) -> dict:
    old={row.designation_id:row for row in previous}; new={row.designation_id:row for row in current}
    common=old.keys()&new.keys(); modified=[]
    for key in sorted(common):
        before=old[key].to_dict(); after=new[key].to_dict()
        comparable=("name","entity_type","programs","effective_date","external_reference")
        if any(before.get(field)!=after.get(field) for field in comparable):
            modified.append({"before":before,"after":after})
    return {
        "added":[new[k].to_dict() for k in sorted(new.keys()-old.keys())],
        "removed":[old[k].to_dict() for k in sorted(old.keys()-new.keys())],
        "modified":modified,
        "unchanged":len(common)-len(modified),
        "legal_effect_requires_authority_specific_review":True,
    }

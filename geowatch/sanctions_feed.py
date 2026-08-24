from __future__ import annotations

import csv
import hashlib
import io
import json
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
    """Parse current UK Sanctions List CSV while tolerating heading changes/aliases."""
    text=payload.decode("utf-8-sig")
    rows=[]
    for item in csv.DictReader(io.StringIO(text)):
        normalized={str(k or "").strip().casefold().replace(" ","_"): str(v or "").strip() for k,v in item.items()}
        ref=normalized.get("unique_id") or normalized.get("unique_id_/_group_id") or normalized.get("group_id") or None
        name=(normalized.get("name") or normalized.get("name_1") or normalized.get("primary_name") or "").strip()
        if not name:
            parts=[normalized.get(k,"") for k in ("name_1","name_2","name_3","name_4","name_5","name_6")]
            name=" ".join(x for x in parts if x).strip()
        if not name: continue
        regime=normalized.get("regime_name") or normalized.get("regime") or normalized.get("sanctions_regime") or ""
        entity_type=normalized.get("type") or normalized.get("individual,_entity,_ship") or normalized.get("designation_type") or "unknown"
        listed=normalized.get("date_designated") or normalized.get("date_designated_/_specified") or normalized.get("last_updated") or None
        did="sanc_"+hashlib.sha256(f"UK|{ref}|{name}|{regime}".encode()).hexdigest()[:20]
        rows.append(SanctionsDesignation(did,"UK-FCDO","UK Sanctions List",ref,name,entity_type,tuple([regime] if regime else []),listed,source_url,collected_at))
    return rows


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

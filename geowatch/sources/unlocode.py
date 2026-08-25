from __future__ import annotations

import csv
import io
from typing import Iterable


def _row(change: str,country: str,location: str,name: str,name_wo: str,subdivision: str,status: str,function: str,date: str="",iata: str="",coordinates: str="",remarks: str="",*,source_release: str) -> dict | None:
    country=str(country or "").strip(); location=str(location or "").strip(); function=str(function or "").strip()
    if not country or not location: return None
    return {
        "source_id":"un_locode","source_release":source_release,"change_indicator":str(change or "").strip(),"country_code":country,
        "location_code":location,"unlocode":f"{country}{location}","location_name":str(name or name_wo or "").strip(),"name_without_diacritics":str(name_wo or "").strip(),
        "subdivision":str(subdivision or "").strip(),"status":str(status or "").strip(),"function":function,"date":str(date or "").strip(),
        "iata":str(iata or "").strip(),"coordinates":str(coordinates or "").strip(),"remarks":str(remarks or "").strip(),
        "is_port":len(function)>=1 and function[0]=="1","is_rail_terminal":len(function)>=2 and function[1]=="2",
        "is_road_terminal":len(function)>=3 and function[2]=="3","is_airport":len(function)>=4 and function[3]=="4",
        "is_fixed_transport_installation":len(function)>=7 and function[6]=="7","is_inland_water_terminal":len(function)>=8 and function[7]=="8",
        "identity_reference_not_criticality_evidence":True,
    }


def parse_unlocode_csv(payload: bytes, *, source_release: str="2025-1") -> list[dict]:
    text=payload.decode("utf-8-sig",errors="replace")
    rows=[]
    first_line=text.splitlines()[0] if text.splitlines() else ""
    header_tokens={token.strip().casefold() for token in next(csv.reader([first_line]),[])}
    headered=bool({"country","location","name"}.issubset(header_tokens))
    if headered:
        for raw in csv.DictReader(io.StringIO(text)):
            norm={str(k or "").strip().casefold().replace("_","").replace(" ",""):v for k,v in raw.items()}
            item=_row(
                norm.get("change") or norm.get("ch"),norm.get("country"),norm.get("location"),norm.get("name"),
                norm.get("namewodiacritics"),norm.get("subdivision") or norm.get("subdiv"),norm.get("status"),norm.get("function"),
                norm.get("date"),norm.get("iata"),norm.get("coordinates"),norm.get("remarks"),source_release=source_release,
            )
            if item: rows.append(item)
        return rows
    for fields in csv.reader(io.StringIO(text)):
        if len(fields)<8: continue
        vals=(fields+[""]*12)[:12]
        # Current official package and historical releases use: Ch, Country, Location, Name, NameWoDiacritics, SubDiv, Function/Status ordering may differ by package.
        change,country,location,name,name_wo,subdivision=vals[:6]
        seventh,eighth=vals[6],vals[7]
        if any(ch.isdigit() for ch in str(seventh)) or "-" in str(seventh): function,status=seventh,eighth
        else: status,function=seventh,eighth
        item=_row(change,country,location,name,name_wo,subdivision,status,function,*vals[8:12],source_release=source_release)
        if item: rows.append(item)
    return rows


def port_rows(rows: Iterable[dict]) -> list[dict]:
    return [dict(r) for r in rows if r.get("is_port")]

from __future__ import annotations

import csv
import io
from typing import Iterable


def parse_unlocode_csv(payload: bytes, *, source_release: str="2025-1") -> list[dict]:
    text=payload.decode("utf-8-sig",errors="replace")
    reader=csv.reader(io.StringIO(text))
    rows=[]
    for fields in reader:
        if len(fields)<8: continue
        # Standard UN/LOCODE CSV releases are distributed without a universal header row.
        change,country,location,name,name_wo,subdivision,function,status,*rest=(fields+[""]*12)[:12]
        if not country or not location or country.casefold() in {"country","ch"}: continue
        function=str(function or "")
        rows.append({
            "source_id":"un_locode","source_release":source_release,"change_indicator":change,"country_code":country.strip(),
            "location_code":location.strip(),"unlocode":f"{country.strip()}{location.strip()}","location_name":name.strip() or name_wo.strip(),
            "subdivision":subdivision.strip(),"function":function,"status":status.strip(),
            "is_port":"1" in function,"is_rail_terminal":"2" in function,"is_road_terminal":"3" in function,"is_airport":"4" in function,
            "identity_reference_not_criticality_evidence":True,
        })
    return rows


def port_rows(rows: Iterable[dict]) -> list[dict]:
    return [dict(r) for r in rows if r.get("is_port")]

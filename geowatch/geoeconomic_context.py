from __future__ import annotations

from collections import defaultdict
from typing import Iterable

REQUIRED_FIELDS=("reference_period","source_id","origin","destination","commodity","value","unit")


def normalize_observations(rows: Iterable[dict]) -> list[dict]:
    out=[]
    for raw in rows:
        row=dict(raw); missing=[field for field in REQUIRED_FIELDS if row.get(field) in (None,"")]
        row["validation_status"]="incomplete" if missing else "valid"
        if missing: row["missing_fields"]=missing
        row["observed_not_conflict_evidence"]=True; out.append(row)
    return out


def dependency_matrix(rows: Iterable[dict], *, commodity: str|None=None, reference_period: str|None=None)->dict:
    values=[r for r in normalize_observations(rows) if r["validation_status"]=="valid"]
    if commodity is not None: values=[r for r in values if str(r.get("commodity"))==commodity]
    if reference_period is not None: values=[r for r in values if str(r.get("reference_period"))==reference_period]
    totals=defaultdict(float); bilateral=defaultdict(float); sources=defaultdict(set)
    for row in values:
        try: value=float(row["value"])
        except (TypeError,ValueError): continue
        origin=str(row["origin"]); dest=str(row["destination"]); key=(origin,dest,str(row["commodity"]),str(row["unit"]))
        bilateral[key]+=value; totals[(origin,str(row["commodity"]),str(row["unit"]))]+=value; sources[key].add(str(row["source_id"]))
    edges=[]
    for key,value in bilateral.items():
        origin,dest,comm,unit=key; total=totals[(origin,comm,unit)]
        edges.append({"origin":origin,"destination":dest,"commodity":comm,"unit":unit,"value":value,"share_of_origin_total":round(value/total,6) if total else None,"source_ids":sorted(sources[key]),"structural_dependency_not_event_probability":True})
    return {"schema_version":"geowatch-geoeconomic-dependency-matrix-v1","edge_count":len(edges),"edges":sorted(edges,key=lambda r:(r["commodity"],-float(r["share_of_origin_total"] or 0))),"missing_data_not_zero_filled":True,"observations_not_conflict_evidence":True}


def attach_country_indicators(country_rows:list[dict],observations:list[dict])->dict:
    latest={}
    for row in observations:
        code=str(row.get("country") or row.get("countryiso3code") or row.get("country_id") or "")
        indicator=str(row.get("indicator") or row.get("indicator_id") or "")
        year=str(row.get("date") or row.get("reference_period") or row.get("reference_year") or "")
        if not code or not indicator: continue
        key=(code,indicator); previous=latest.get(key)
        prev_year=str((previous or {}).get("date") or (previous or {}).get("reference_period") or (previous or {}).get("reference_year") or "")
        if previous is None or year>prev_year: latest[key]=row
    countries=[]
    for country in country_rows:
        code=str(country.get("id") or country.get("country_id") or country.get("iso3Code") or "")
        countries.append({**country,"geoeconomic_indicators":[dict(v) for (c,_),v in latest.items() if c==code],"context_not_evidence":True})
    return {"schema_version":"geowatch-country-geoeconomic-context-v1","country_count":len(countries),"countries":countries,"indicators_are_context_not_conflict_evidence":True}

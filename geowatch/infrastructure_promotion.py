from __future__ import annotations

from typing import Iterable

IDENTITY_SOURCES={"nga_world_port_index","un_locode"}
STRATEGIC_SOURCE_TYPES={"official_chokepoint","port_authority","dated_trade_flow","dated_energy_flow","critical_corridor"}


def normalize_port_key(name: str | None, country: str | None) -> str:
    return "|".join((str(country or "").strip().casefold(),str(name or "").strip().casefold()))


def corroborate_ports(wpi_rows: Iterable[dict], unlocode_rows: Iterable[dict], strategic_evidence: Iterable[dict]=()) -> dict:
    wpi={normalize_port_key(r.get("port_name") or r.get("name"),r.get("country") or r.get("country_code")):r for r in wpi_rows}
    loc={normalize_port_key(r.get("location_name") or r.get("name"),r.get("country") or r.get("country_code")):r for r in unlocode_rows}
    strategic={}
    for row in strategic_evidence:
        strategic.setdefault(normalize_port_key(row.get("port_name") or row.get("name"),row.get("country") or row.get("country_code")),[]).append(row)
    nodes=[]
    for key in sorted(set(wpi)|set(loc)):
        sources=[]
        if key in wpi: sources.append("nga_world_port_index")
        if key in loc: sources.append("un_locode")
        evidence=strategic.get(key,[])
        strategic_types=sorted({str(r.get("evidence_type")) for r in evidence if r.get("evidence_type")})
        identity_corroborated=IDENTITY_SOURCES.issubset(set(sources))
        strategic_supported=any(t in STRATEGIC_SOURCE_TYPES for t in strategic_types)
        status="reviewed_critical" if identity_corroborated and strategic_supported else "identity_corroborated" if identity_corroborated else "candidate"
        base=wpi.get(key) or loc.get(key) or {}
        nodes.append({
            "port_key":key,"port_name":base.get("port_name") or base.get("location_name") or base.get("name"),"country":base.get("country") or base.get("country_code"),
            "status":status,"identity_sources":sources,"identity_corroborated":identity_corroborated,
            "strategic_evidence_types":strategic_types,"strategic_supported":strategic_supported,
            "criticality_not_inferred_from_identity_sources_alone":True,
        })
    return {"schema_version":"geowatch-infrastructure-promotion-v1","node_count":len(nodes),"reviewed_critical_count":sum(r["status"]=="reviewed_critical" for r in nodes),"identity_corroborated_count":sum(r["identity_corroborated"] for r in nodes),"nodes":nodes}

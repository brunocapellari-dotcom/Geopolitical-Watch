from __future__ import annotations


def review_wpi_candidates(nodes: list[dict], *, minimum_authoritative_sources: int = 2) -> dict:
    rows=[]
    for node in nodes:
        facilities=set(node.get("facilities") or [])
        structural_signals=sum([
            str(node.get("harbor_size") or "").casefold()=="large",
            "Container" in facilities,"Oil Terminal" in facilities,"LNG Terminal" in facilities,
        ])
        existing_sources=set(node.get("source_ids") or ["nga_wpi"])
        rows.append({
            **node,
            "structural_signal_count":structural_signals,
            "authoritative_source_count":len(existing_sources),
            "promotion_status":"review_ready" if structural_signals>=2 else "candidate",
            "promoted_to_reviewed_critical":bool(structural_signals>=2 and len(existing_sources)>=minimum_authoritative_sources),
            "additional_authoritative_source_required":len(existing_sources)<minimum_authoritative_sources,
            "criticality_probability":None,
            "current_operational_status":None,
        })
    return {
        "schema_version":"geowatch-infrastructure-promotion-review-v1",
        "candidate_count":len(rows),
        "review_ready_count":sum(r["promotion_status"]=="review_ready" for r in rows),
        "reviewed_critical_count":sum(r["promoted_to_reviewed_critical"] for r in rows),
        "nodes":rows,
        "governance":{"wpi_is_authoritative_structural_port_data":True,"single_source_heuristic_cannot_establish_geopolitical_criticality":True,"live_status_requires_current_authority_or_notice":True},
    }

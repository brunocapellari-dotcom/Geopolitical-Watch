from __future__ import annotations

from typing import Iterable, Mapping


def route_exposure(route_shares: Mapping[str, float], *, disrupted_nodes: Iterable[str], alternatives: Mapping[str, list[str]] | None = None) -> dict:
    """Compute structural route exposure without claiming realized disruption/loss."""
    alternatives = alternatives or {}
    clean = {str(k): max(0.0, float(v)) for k, v in route_shares.items()}
    total = sum(clean.values())
    shares = {k: (v / total if total else 0.0) for k, v in clean.items()}
    disrupted = set(disrupted_nodes)
    affected = sum(share for node, share in shares.items() if node in disrupted)
    alt_map = {node: alternatives.get(node, []) for node in disrupted if node in shares}
    unmitigated = sum(shares[node] for node in disrupted if node in shares and not alt_map.get(node))
    return {
        "schema_version": "geowatch-chokepoint-exposure-v1",
        "affected_route_share": round(affected, 6),
        "unmitigated_route_share": round(unmitigated, 6),
        "affected_nodes": sorted(disrupted & set(shares)),
        "alternatives": alt_map,
        "route_shares": {k: round(v, 6) for k, v in sorted(shares.items())},
        "structural_exposure_not_loss_forecast": True,
    }


def scenario_matrix(cases: Iterable[dict]) -> list[dict]:
    rows = []
    for case in cases:
        rows.append({
            "scenario_id": case["scenario_id"],
            **route_exposure(case.get("route_shares", {}), disrupted_nodes=case.get("disrupted_nodes", []), alternatives=case.get("alternatives", {})),
        })
    return sorted(rows, key=lambda row: row["affected_route_share"], reverse=True)


def portfolio_exposure(country_routes: Mapping[str, Mapping[str, float]], disrupted_nodes: Iterable[str]) -> list[dict]:
    disrupted = list(disrupted_nodes)
    result=[]
    for country, shares in country_routes.items():
        row=route_exposure(shares, disrupted_nodes=disrupted)
        result.append({"country":country, **row})
    return sorted(result, key=lambda row: row["affected_route_share"], reverse=True)

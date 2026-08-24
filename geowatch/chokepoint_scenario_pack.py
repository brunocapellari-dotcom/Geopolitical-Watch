from __future__ import annotations

from typing import Mapping

from .chokepoints import route_exposure


def build_scenario_pack(
    *,
    scenario_id: str,
    route_shares: Mapping[str, float],
    disrupted_nodes: list[str],
    alternatives: Mapping[str, list[str]] | None = None,
    route_share_uncertainty: float = 0.10,
    alternative_absorption: Mapping[str, float] | None = None,
    additional_distance_pct: Mapping[str, float] | None = None,
) -> dict:
    """Create a structural disruption scenario with explicit uncertainty.

    Inputs such as route shares and alternative absorption must be dated externally.
    The result is an exposure scenario, not a forecast that the disruption will occur.
    """
    base = route_exposure(route_shares, disrupted_nodes=disrupted_nodes, alternatives=alternatives or {})
    uncertainty = max(0.0, min(0.75, float(route_share_uncertainty)))
    affected = float(base["affected_route_share"])
    low = max(0.0, affected * (1.0 - uncertainty))
    high = min(1.0, affected * (1.0 + uncertainty))
    absorption = {str(k): max(0.0, min(1.0, float(v))) for k, v in (alternative_absorption or {}).items()}
    distance = {str(k): max(0.0, float(v)) for k, v in (additional_distance_pct or {}).items()}
    residual = 0.0
    for node, share in base["route_shares"].items():
        if node not in set(disrupted_nodes):
            continue
        residual += float(share) * (1.0 - absorption.get(node, 0.0))
    weighted_distance = sum(float(base["route_shares"].get(node, 0.0)) * distance.get(node, 0.0) for node in disrupted_nodes)
    return {
        "schema_version": "geowatch-chokepoint-scenario-pack-v1",
        "scenario_id": scenario_id,
        "disrupted_nodes": sorted(set(disrupted_nodes)),
        "affected_route_share": affected,
        "affected_route_share_band": {"low": round(low, 6), "base": round(affected, 6), "high": round(high, 6)},
        "residual_share_after_assumed_alternative_absorption": round(residual, 6),
        "weighted_additional_distance_pct": round(weighted_distance, 6),
        "alternatives": base["alternatives"],
        "alternative_absorption_assumptions": absorption,
        "additional_distance_pct_assumptions": distance,
        "input_uncertainty_fraction": uncertainty,
        "structural_exposure_not_event_probability": True,
        "requires_dated_route_share_inputs": True,
    }

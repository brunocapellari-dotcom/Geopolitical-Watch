from __future__ import annotations

from typing import Iterable, Mapping


def concentration_hhi(shares: Iterable[float]) -> float:
    values = [float(x) for x in shares if float(x) >= 0]
    total = sum(values)
    if total <= 0:
        return 0.0
    normalized = [x / total for x in values]
    return round(sum(x * x for x in normalized), 6)


def effective_suppliers(shares: Iterable[float]) -> float | None:
    hhi = concentration_hhi(shares)
    return round(1.0 / hhi, 3) if hhi > 0 else None


def dependency_score(*, import_share_of_consumption: float, supplier_shares: Iterable[float],
                     route_shares: Iterable[float] = (), substitution_score: float = 0.5) -> dict:
    for value in (import_share_of_consumption, substitution_score):
        if not 0 <= value <= 1:
            raise ValueError("shares/scores must be in [0,1]")
    supplier_hhi = concentration_hhi(supplier_shares)
    route_hhi = concentration_hhi(route_shares) if list(route_shares) else 0.0
    scarcity = 1.0 - substitution_score
    raw = import_share_of_consumption * (0.45 + 0.30 * supplier_hhi + 0.15 * route_hhi + 0.10 * scarcity)
    return {
        "dependency_index": round(min(1.0, raw), 4),
        "supplier_hhi": supplier_hhi,
        "route_hhi": route_hhi,
        "effective_suppliers": effective_suppliers(supplier_shares),
        "substitution_score": substitution_score,
        "methodology_notes": [
            "This is a structural exposure index, not a forecast of disruption or economic loss.",
            "Input shares must be dated and sourced; stale trade/energy data can materially change the result.",
            "Physical substitutability, contracts, inventories, spare capacity and policy response require separate analysis.",
        ],
    }


def chokepoint_exposure(route_shares: Mapping[str, float], disrupted_routes: Iterable[str]) -> dict:
    disrupted = set(disrupted_routes)
    total = sum(max(0.0, float(v)) for v in route_shares.values())
    affected = sum(max(0.0, float(v)) for k, v in route_shares.items() if k in disrupted)
    share = affected / total if total > 0 else 0.0
    return {
        "affected_route_share": round(share, 4),
        "affected_routes": sorted(disrupted & set(route_shares)),
        "route_hhi": concentration_hhi(route_shares.values()),
        "impact_not_loss_estimate": True,
    }


def dependency_matrix(rows: Iterable[dict]) -> list[dict]:
    result = []
    for row in rows:
        metrics = dependency_score(
            import_share_of_consumption=float(row.get("import_share_of_consumption", 0)),
            supplier_shares=row.get("supplier_shares", []),
            route_shares=row.get("route_shares", []),
            substitution_score=float(row.get("substitution_score", 0.5)),
        )
        result.append({**row, **metrics})
    return sorted(result, key=lambda row: float(row["dependency_index"]), reverse=True)

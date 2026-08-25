from __future__ import annotations


def build_failover_plan(source_id: str, error: str, policy: dict) -> dict:
    row=next((r for r in policy.get("sources",[]) if r.get("source_id")==source_id),{})
    text=str(error or "").casefold()
    transient=any(t in text for t in ("429","502","503","504","timeout","timed out","connection"))
    actions=[]
    if transient:
        for step in row.get("transient_steps",[]): actions.append(dict(step))
    else:
        for step in row.get("structural_steps",[]): actions.append(dict(step))
    return {
        "schema_version":"geowatch-failover-plan-v1","source_id":source_id,"transient":transient,
        "actions":actions,"independent_corroboration_count":0,
        "same_provider_fallback_never_counts_as_independent_corroboration":True,
        "context_only_sources_never_replace_conflict_evidence":True,
    }

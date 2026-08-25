from __future__ import annotations

from datetime import datetime


def _date(value: str | None):
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace("Z","+00:00")).date()
    except ValueError: return None


def evaluate_v1_gate(*, config: dict, readiness: dict, external_evidence: dict, human_gold: dict, prospective_score: dict, source_history: dict, infrastructure: dict) -> dict:
    minimums=config.get("minimums",{})
    obs=list(source_history.get("observations") or [])
    days={_date(r.get("observed_at")) for r in obs}; days.discard(None)
    checks=[]
    checks.append({"id":"readiness_threshold","passed":float(readiness.get("weighted_readiness") or 0)>=float(config.get("readiness_threshold",0.95)),"value":readiness.get("weighted_readiness")})
    checks.append({"id":"human_gold","passed":int(human_gold.get("human_gold_count") or 0)>=int(minimums.get("human_gold",500)),"value":human_gold.get("human_gold_count",0)})
    checks.append({"id":"resolved_prospective_forecasts","passed":int(prospective_score.get("resolved_count") or 0)>=int(minimums.get("resolved_prospective_forecasts",200)),"value":prospective_score.get("resolved_count",0)})
    checks.append({"id":"source_history_days","passed":len(days)>=int(minimums.get("source_history_days",30)),"value":len(days)})
    checks.append({"id":"reviewed_critical_infrastructure","passed":int(infrastructure.get("reviewed_critical_count") or 0)>=int(minimums.get("reviewed_critical_infrastructure",50)),"value":infrastructure.get("reviewed_critical_count",0)})
    for gate in config.get("external_evidence_required",[]):
        evidence=external_evidence.get(gate) or {}
        checks.append({"id":gate,"passed":bool(evidence.get("passed")) and bool(evidence.get("artifact_id") or evidence.get("evidence_uri")),"artifact_id":evidence.get("artifact_id"),"external":True})
    passed=all(r["passed"] for r in checks)
    return {"schema_version":"geowatch-v1-gate-v1","checks":checks,"passed":passed,"release_candidate_allowed":passed,"no_self_attestation":True,"retrospective_benchmarks_do_not_close_prospective_gate":True}

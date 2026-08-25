from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def classify_operational_health(*, source_results: list[dict], coverage: dict, max_stale_hours: float = 6.0) -> dict:
    structural=[]; transient=[]; ok=[]
    for row in source_results:
        if row.get("status") == "ok":
            ok.append(row.get("source_id")); continue
        error=str(row.get("error") or "")
        target=transient if any(token in error.casefold() for token in ("429","timeout","timed out","502","503","504","connection")) else structural
        target.append({"source_id":row.get("source_id"),"error":error})
    source_rows=list(coverage.get("sources") or [])
    latest=[]
    now=datetime.now(timezone.utc)
    for row in source_rows:
        value=row.get("last_reference_in_bounded_sample")
        if not value: continue
        try:
            dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            latest.append(max(0.0,(now-dt).total_seconds()/3600.0))
        except ValueError:
            pass
    stale=bool(latest and min(latest)>max_stale_hours)
    if structural: status="failed"
    elif not ok: status="partial"
    elif stale: status="stale"
    elif transient: status="degraded"
    elif len(ok)<len(source_results): status="partial"
    else: status="healthy"
    return {
        "schema_version":"geowatch-operational-health-v1",
        "status":status,
        "healthy":status=="healthy",
        "degraded":status in {"degraded","stale","partial","failed"},
        "stale":stale,
        "ok_sources":[x for x in ok if x],
        "transient_errors":transient,
        "structural_errors":structural,
        "freshness_hours_best":round(min(latest),3) if latest else None,
        "freshness_hours_worst":round(max(latest),3) if latest else None,
        "health_is_operational_not_evidence_strength":True,
    }


def build_operational_snapshot(*, generated_at: str, source_results: list[dict], coverage: dict, episode_report: dict, alerts_generated: int = 0, alerts_enqueued: int = 0) -> dict:
    health=classify_operational_health(source_results=source_results,coverage=coverage)
    episodes=[]
    for row in episode_report.get("episodes",[]):
        episodes.append({
            "episode_id":row.get("episode_id"),"title":row.get("title"),"state":row.get("state"),
            "last_updated_at":row.get("last_updated_at"),"countries":list(row.get("countries") or []),
            "change_flags":list(row.get("change_flags") or []),
            "evidence_strength_index":(row.get("evidence_strength") or {}).get("overall_index"),
        })
    raw=f"{generated_at}|{health['status']}|"+"|".join(sorted(str(x.get('episode_id')) for x in episodes))
    return {
        "schema_version":"geowatch-operational-snapshot-v1",
        "snapshot_id":"ops_"+hashlib.sha256(raw.encode()).hexdigest()[:20],
        "generated_at":generated_at,"health":health,"source_results":source_results,
        "episode_count":len(episodes),"episodes":episodes,"alerts_generated":alerts_generated,"alerts_enqueued":alerts_enqueued,
        "coverage":coverage,
    }


def compare_snapshots(previous: dict | None, current: dict) -> dict:
    if not previous:
        return {"schema_version":"geowatch-operational-delta-v1","baseline":True,"from_snapshot":None,"to_snapshot":current.get("snapshot_id"),"changes":[]}
    old={r["episode_id"]:r for r in previous.get("episodes",[]) if r.get("episode_id")}
    new={r["episode_id"]:r for r in current.get("episodes",[]) if r.get("episode_id")}
    changes=[]
    for eid in sorted(new.keys()-old.keys()):
        changes.append({"type":"new_episode","episode_id":eid,"title":new[eid].get("title")})
    for eid in sorted(old.keys()-new.keys()):
        changes.append({"type":"episode_not_in_current_window","episode_id":eid,"title":old[eid].get("title")})
    for eid in sorted(old.keys() & new.keys()):
        before,after=old[eid],new[eid]
        if before.get("state")!=after.get("state"):
            changes.append({"type":"state_changed","episode_id":eid,"from":before.get("state"),"to":after.get("state")})
        old_flags=set(before.get("change_flags") or []); new_flags=set(after.get("change_flags") or [])
        for flag in sorted(new_flags-old_flags):
            changes.append({"type":"new_change_flag","episode_id":eid,"flag":flag})
        b=before.get("evidence_strength_index"); a=after.get("evidence_strength_index")
        if isinstance(a,(int,float)) and isinstance(b,(int,float)) and abs(a-b)>=5:
            changes.append({"type":"evidence_strength_shift","episode_id":eid,"from":b,"to":a,"not_probability":True})
    old_sources={r.get("source_id"):r.get("status") for r in previous.get("source_results",[])}
    new_sources={r.get("source_id"):r.get("status") for r in current.get("source_results",[])}
    for sid in sorted(set(old_sources)|set(new_sources)):
        if old_sources.get(sid)!=new_sources.get(sid):
            changes.append({"type":"source_status_changed","source_id":sid,"from":old_sources.get(sid),"to":new_sources.get(sid)})
    return {
        "schema_version":"geowatch-operational-delta-v1","baseline":False,
        "from_snapshot":previous.get("snapshot_id"),"to_snapshot":current.get("snapshot_id"),
        "health_from":(previous.get("health") or {}).get("status"),"health_to":(current.get("health") or {}).get("status"),
        "changes":changes,"change_count":len(changes),
    }


def append_history(history: dict | None, snapshot: dict, *, max_entries: int = 720) -> dict:
    rows=list((history or {}).get("snapshots") or [])
    if not rows or rows[-1].get("snapshot_id")!=snapshot.get("snapshot_id"):
        rows.append(snapshot)
    rows=rows[-max_entries:]
    return {"schema_version":"geowatch-operational-history-v1","snapshot_count":len(rows),"snapshots":rows,"bounded":True,"max_entries":max_entries}

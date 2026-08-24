from __future__ import annotations

from datetime import datetime, timedelta, timezone


def operational_snapshot(store, *, now: datetime | None = None) -> dict[str, object]:
    now = now or datetime.now(timezone.utc)
    day_start = (now - timedelta(hours=24)).isoformat()
    runs = store.recent_runs(limit=500)
    episodes = store.list_episode_records(limit=1000)
    changes = store.changes_since(day_start, limit=5000)
    pending = store.pending_alerts(limit=1000) if hasattr(store, "pending_alerts") else []
    ok_runs = sum(1 for row in runs if row.get("status") == "ok")
    error_runs = sum(1 for row in runs if row.get("status") == "error")
    states: dict[str, int] = {}
    for episode in episodes:
        state = str(episode.get("state") or "unknown")
        states[state] = states.get(state, 0) + 1
    return {
        "generated_at": now.isoformat(),
        "collector_runs_total": len(runs),
        "collector_runs_ok": ok_runs,
        "collector_runs_error": error_runs,
        "episodes_total": len(episodes),
        "episodes_by_state": states,
        "changes_24h": len(changes),
        "pending_alerts": len(pending),
    }


def prometheus_text(snapshot: dict[str, object]) -> str:
    lines = [
        "# HELP geowatch_collector_runs_total Collector runs retained in the operational window.",
        "# TYPE geowatch_collector_runs_total gauge",
        f"geowatch_collector_runs_total {int(snapshot.get('collector_runs_total', 0))}",
        "# HELP geowatch_collector_runs_error Collector runs with error status.",
        "# TYPE geowatch_collector_runs_error gauge",
        f"geowatch_collector_runs_error {int(snapshot.get('collector_runs_error', 0))}",
        "# HELP geowatch_episodes_total Persisted conflict episodes.",
        "# TYPE geowatch_episodes_total gauge",
        f"geowatch_episodes_total {int(snapshot.get('episodes_total', 0))}",
        "# HELP geowatch_episode_changes_24h Episode state/lineage changes in the last 24 hours.",
        "# TYPE geowatch_episode_changes_24h gauge",
        f"geowatch_episode_changes_24h {int(snapshot.get('changes_24h', 0))}",
        "# HELP geowatch_pending_alerts Pending alerts in the outbox.",
        "# TYPE geowatch_pending_alerts gauge",
        f"geowatch_pending_alerts {int(snapshot.get('pending_alerts', 0))}",
    ]
    states = snapshot.get("episodes_by_state") or {}
    if isinstance(states, dict):
        lines += ["# HELP geowatch_episodes_by_state Persisted episodes by deterministic state.", "# TYPE geowatch_episodes_by_state gauge"]
        for state, count in sorted(states.items()):
            lines.append(f'geowatch_episodes_by_state{{state="{state}"}} {int(count)}')
    return "\n".join(lines) + "\n"

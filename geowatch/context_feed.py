from __future__ import annotations

from datetime import datetime, timedelta, timezone


def build_context_feed(
    store,
    *,
    source_ids: set[str],
    hours: int = 24,
    limit: int = 1000,
) -> dict[str, object]:
    bounded_hours = max(1, min(int(hours), 24 * 30))
    bounded_limit = max(1, min(int(limit), 5000))
    since = (datetime.now(timezone.utc) - timedelta(hours=bounded_hours)).isoformat()
    rows = [event for event in store.load_events_since(since) if event.source_id in source_ids]
    rows.sort(key=lambda event: (event.reference_at, event.event_id), reverse=True)
    rows = rows[:bounded_limit]
    return {
        "schema_version": "geowatch-context-feed-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hours": bounded_hours,
        "source_ids": sorted(source_ids),
        "event_count": len(rows),
        "events": [event.to_dict() for event in rows],
        "semantics": {
            "context_only": True,
            "attribution": "Context observations do not establish conflict cause, actor, intent, cyberattack, or military attribution by themselves.",
        },
    }

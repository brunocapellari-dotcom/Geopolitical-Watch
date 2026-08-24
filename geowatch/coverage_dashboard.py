from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone


def build_source_coverage_dashboard(store, *, run_limit: int = 1000, event_limit: int = 1000) -> dict:
    """Build a bounded operational coverage view from the common store contract.

    This is intentionally a dashboard of what the system has collected, not a claim
    about the provider's complete historical archive. For very large stores, the
    event sample is bounded and the response marks that limitation explicitly.
    """
    runs = store.recent_runs(limit=run_limit)
    events = store.list_events(limit=event_limit)
    by_source: dict[str, dict] = {}
    event_dates: dict[str, list[str]] = defaultdict(list)
    event_counts: dict[str, int] = defaultdict(int)
    for event in events:
        source_id = str(event.get("source_id") or "unknown")
        event_counts[source_id] += 1
        if event.get("reference_at"):
            event_dates[source_id].append(str(event["reference_at"]))
    run_groups: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        run_groups[str(run.get("source_id") or "unknown")].append(run)
    source_ids = sorted(set(event_counts) | set(run_groups))
    for source_id in source_ids:
        group = sorted(run_groups.get(source_id, []), key=lambda row: str(row.get("started_at") or ""), reverse=True)
        dates = sorted(event_dates.get(source_id, []))
        successful = [row for row in group if row.get("status") == "ok"]
        failed = [row for row in group if row.get("status") != "ok"]
        last = group[0] if group else None
        by_source[source_id] = {
            "source_id": source_id,
            "events_in_bounded_sample": event_counts.get(source_id, 0),
            "first_reference_in_bounded_sample": dates[0] if dates else None,
            "last_reference_in_bounded_sample": dates[-1] if dates else None,
            "runs_in_bounded_sample": len(group),
            "successful_runs": len(successful),
            "failed_runs": len(failed),
            "last_run_started_at": last.get("started_at") if last else None,
            "last_run_status": last.get("status") if last else None,
            "last_run_records": last.get("records") if last else None,
        }
    return {
        "schema_version": "geowatch-source-coverage-dashboard-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [by_source[key] for key in sorted(by_source)],
        "run_limit": run_limit,
        "event_limit": event_limit,
        "bounded_view": True,
        "coverage_not_provider_archive_claim": True,
    }

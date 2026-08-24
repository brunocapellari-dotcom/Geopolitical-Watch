from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import ConflictEpisode, Event, EvidenceRef


def source_coverage_inventory(store, *, run_limit: int = 5000) -> dict:
    """Summarize observed collector coverage from durable audit records.

    This measures what Geopolitical Watch actually collected, not what a provider
    theoretically offers historically.
    """
    grouped: dict[str, dict] = defaultdict(lambda: {
        "runs": 0,
        "successful_runs": 0,
        "failed_runs": 0,
        "records": 0,
        "first_run_at": None,
        "last_run_at": None,
        "last_success_at": None,
        "last_error": None,
    })
    for row in store.recent_runs(limit=run_limit):
        source_id = str(row["source_id"])
        item = grouped[source_id]
        item["runs"] += 1
        started = row.get("started_at")
        item["first_run_at"] = _min_iso(item["first_run_at"], started)
        item["last_run_at"] = _max_iso(item["last_run_at"], started)
        if row.get("status") == "ok":
            item["successful_runs"] += 1
            item["records"] += int(row.get("records") or 0)
            item["last_success_at"] = _max_iso(item["last_success_at"], row.get("finished_at"))
        else:
            item["failed_runs"] += 1
            if row.get("error"):
                item["last_error"] = row.get("error")
    rows = []
    for source_id, item in sorted(grouped.items()):
        runs = item["runs"] or 1
        item["success_rate"] = round(item["successful_runs"] / runs, 4)
        item["source_id"] = source_id
        checkpoint = store.get_checkpoint(source_id)
        item["checkpoint"] = checkpoint
        rows.append(item)
    return {"schema_version": "geowatch-coverage-inventory-v1", "sources": rows}


def calibrate_binary_alerts(rows: Iterable[dict]) -> dict:
    """Compute transparent binary alert calibration metrics.

    Expected rows contain `predicted` and `actual` booleans. Optional `score`
    values are retained only for future threshold analysis and do not affect the
    confusion matrix here.
    """
    tp = fp = tn = fn = 0
    count = 0
    for row in rows:
        predicted = bool(row.get("predicted"))
        actual = bool(row.get("actual"))
        count += 1
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    false_positive_rate = fp / (fp + tn) if fp + tn else None
    return {
        "schema_version": "geowatch-alert-calibration-v1",
        "n": count,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": _round_or_none(precision),
        "recall": _round_or_none(recall),
        "false_positive_rate": _round_or_none(false_positive_rate),
    }


def episode_quality_flags(
    episode: ConflictEpisode,
    *,
    events: Iterable[Event] = (),
    evidence: Iterable[EvidenceRef] = (),
) -> list[str]:
    event_rows = list(events)
    evidence_rows = list(evidence)
    flags: list[str] = []
    strength = episode.evidence_strength.overall_index if episode.evidence_strength else 0
    if strength < 25:
        flags.append("low_evidence_strength")
    providers = {row.provider or row.source_id for row in evidence_rows if row.evidence_id in episode.evidence_ids}
    if len(providers) <= 1:
        flags.append("single_provider_or_unresolved_independence")
    if not episode.countries and not any(row.country for row in event_rows):
        flags.append("geography_unresolved")
    if "contradiction_present" in episode.change_flags:
        flags.append("contradiction_present")
    if "retraction_present" in episode.change_flags:
        flags.append("retraction_present")
    if episode.state == "emerging":
        flags.append("emerging_episode")
    return flags


def _round_or_none(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _min_iso(current, value):
    if not value:
        return current
    return value if current is None or value < current else current


def _max_iso(current, value):
    if not value:
        return current
    return value if current is None or value > current else current

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

DEFAULT_OUTCOMES = (
    "ceasefire",
    "territorial_change",
    "regime_change",
    "withdrawal",
    "peace_agreement",
)


def build_base_rate_forecasts(cases: Iterable[dict], *, outcome_tags: tuple[str, ...] = DEFAULT_OUTCOMES, min_prior_cases: int = 8) -> list[dict]:
    """Create a leakage-safe retrospective benchmark.

    For every completed case, probabilities are estimated only from cases that
    had already ended before the target case began. This is a baseline benchmark,
    not a claim that the live forecasting engine issued these forecasts historically.
    """
    rows = sorted((dict(row) for row in cases if row.get("start")), key=lambda r: r["start"])
    forecasts: list[dict] = []
    for case in rows:
        start = _date(case["start"])
        end_raw = case.get("end")
        if not end_raw:
            continue
        end = _date(str(end_raw))
        prior = [row for row in rows if row.get("end") and _date(str(row["end"])) < start]
        if len(prior) < min_prior_cases:
            continue
        counts = Counter(tag for row in prior for tag in row.get("outcome_tags", []))
        for tag in outcome_tags:
            p = (counts.get(tag, 0) + 1.0) / (len(prior) + 2.0)  # Laplace smoothing
            outcome = 1 if tag in set(case.get("outcome_tags", [])) else 0
            horizon_days = max(1, (end - start).days)
            created = datetime.combine(start - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
            resolved = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)
            forecasts.append({
                "forecast_id": f"baseline:{case['case_id']}:{tag}",
                "case_id": case["case_id"],
                "question": f"Will the case resolve with outcome tag '{tag}'?",
                "probability": round(p, 6),
                "outcome": outcome,
                "created_at": created.isoformat(),
                "information_cutoff": created.isoformat(),
                "resolved_at": resolved.isoformat(),
                "horizon_days": horizon_days,
                "benchmark_type": "historical_base_rate",
                "not_a_record_of_live_historical_forecast": True,
            })
    return forecasts


def baseline_summary(forecasts: Iterable[dict]) -> dict:
    rows = list(forecasts)
    if not rows:
        return {"count": 0, "brier_score": None}
    brier = sum((float(row["probability"]) - int(row["outcome"])) ** 2 for row in rows) / len(rows)
    by_tag: dict[str, list[dict]] = {}
    for row in rows:
        tag = str(row["forecast_id"]).rsplit(":", 1)[-1]
        by_tag.setdefault(tag, []).append(row)
    return {
        "schema_version": "geowatch-historical-baseline-summary-v1",
        "count": len(rows),
        "brier_score": round(brier, 6),
        "by_outcome": {
            tag: {
                "count": len(values),
                "brier_score": round(sum((float(v["probability"]) - int(v["outcome"])) ** 2 for v in values) / len(values), 6),
            }
            for tag, values in sorted(by_tag.items())
        },
        "benchmark_only": True,
    }


def _date(value: str) -> date:
    return date.fromisoformat(value[:10])

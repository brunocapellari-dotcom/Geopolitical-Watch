from __future__ import annotations

from math import sqrt
from typing import Iterable


def brier_score(forecasts: Iterable[dict]) -> float | None:
    rows = [row for row in forecasts if row.get("status") == "resolved" and row.get("outcome") in (0, 1)]
    if not rows:
        return None
    return sum((float(row["probability"]) - int(row["outcome"])) ** 2 for row in rows) / len(rows)


def calibration_table(forecasts: Iterable[dict], *, bins: int = 10) -> list[dict]:
    if bins < 2:
        raise ValueError("bins must be >= 2")
    rows = [row for row in forecasts if row.get("status") == "resolved" and row.get("outcome") in (0, 1)]
    result = []
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        bucket = [row for row in rows if low <= float(row["probability"]) < high or (index == bins - 1 and float(row["probability"]) == 1.0)]
        if not bucket:
            continue
        mean_p = sum(float(row["probability"]) for row in bucket) / len(bucket)
        outcome_rate = sum(int(row["outcome"]) for row in bucket) / len(bucket)
        result.append({
            "bin_low": round(low, 3), "bin_high": round(high, 3), "count": len(bucket),
            "mean_probability": round(mean_p, 4), "observed_rate": round(outcome_rate, 4),
            "calibration_error": round(abs(mean_p - outcome_rate), 4),
        })
    return result


def forecast_summary(forecasts: Iterable[dict]) -> dict:
    rows = list(forecasts)
    resolved = [row for row in rows if row.get("status") == "resolved" and row.get("outcome") in (0, 1)]
    score = brier_score(resolved)
    if not resolved:
        return {"count": len(rows), "resolved": 0, "brier_score": None, "rmse_probability_error": None, "calibration": []}
    return {
        "count": len(rows),
        "resolved": len(resolved),
        "brier_score": round(score, 6) if score is not None else None,
        "rmse_probability_error": round(sqrt(score), 6) if score is not None else None,
        "calibration": calibration_table(resolved),
        "methodology_notes": [
            "Brier score evaluates probabilistic binary forecasts; lower is better.",
            "Forecasts must be timestamped before resolution and retain original probability and rationale.",
            "Historical accuracy does not guarantee future accuracy; regime and selection effects must be reviewed.",
        ],
    }

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _dt(value: str) -> datetime:
    text = value if "T" in value else value + "T00:00:00+00:00"
    value_dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return value_dt if value_dt.tzinfo else value_dt.replace(tzinfo=timezone.utc)


class BackfillPlanner:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    @classmethod
    def from_json(cls, path: str | Path = "config/operations/backfill_plan.json") -> "BackfillPlanner":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def windows(self, source_id: str, *, activation_ready: bool = True, limit: int | None = None) -> list[dict]:
        job = next((row for row in self.payload.get("jobs", []) if row["source_id"] == source_id), None)
        if job is None:
            raise KeyError(source_id)
        if job.get("requires_activation") and not activation_ready:
            return []
        start, end = _dt(job["start"]), _dt(job["end"])
        step = timedelta(hours=max(1, int(job.get("chunk_hours", 24))))
        rows: list[dict] = []
        cursor = start
        while cursor < end:
            window_end = min(end, cursor + step)
            rows.append({
                "source_id": source_id,
                "start": cursor.isoformat(),
                "end": window_end.isoformat(),
                "priority": int(job.get("priority", 9)),
                "regional_only": bool(job.get("regional_only")),
                "raw_snapshot_required": True,
            })
            if limit is not None and len(rows) >= limit:
                break
            cursor = window_end
        return rows

    def queue(self, activation_status: dict | None = None, *, per_source_limit: int | None = None) -> list[dict]:
        ready = set((activation_status or {}).get("ready_sources", []))
        rows: list[dict] = []
        for job in self.payload.get("jobs", []):
            source_id = job["source_id"]
            activation_ready = (not job.get("requires_activation")) or source_id in ready
            rows.extend(self.windows(source_id, activation_ready=activation_ready, limit=per_source_limit))
        return sorted(rows, key=lambda row: (row["priority"], row["source_id"], row["start"]))

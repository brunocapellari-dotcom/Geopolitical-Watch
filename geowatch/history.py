from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterator


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime

    def gdelt_params(self) -> dict[str, str]:
        return {
            "startdatetime": self.start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "enddatetime": self.end.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
        }


def parse_utc(value: str) -> datetime:
    text = value.strip()
    if len(text) == 10:
        return datetime.combine(date.fromisoformat(text), datetime.min.time(), tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iter_windows(start: str | datetime, end: str | datetime, *, hours: int = 6) -> Iterator[TimeWindow]:
    if hours < 1:
        raise ValueError("hours must be >= 1")
    current = parse_utc(start) if isinstance(start, str) else _utc(start)
    finish = parse_utc(end) if isinstance(end, str) else _utc(end)
    if finish <= current:
        raise ValueError("end must be after start")
    step = timedelta(hours=hours)
    while current < finish:
        window_end = min(finish, current + step)
        yield TimeWindow(current, window_end)
        current = window_end


def overlap_start(last_success_at: str | None, *, default_lookback_hours: int = 24, overlap_minutes: int = 30, now: datetime | None = None) -> datetime:
    now_utc = _utc(now or datetime.now(timezone.utc))
    if last_success_at:
        return parse_utc(last_success_at) - timedelta(minutes=max(0, overlap_minutes))
    return now_utc - timedelta(hours=max(1, default_lookback_hours))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

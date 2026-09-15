from __future__ import annotations

import threading
import time

_WINDOW_SECONDS = 10 * 60
_MAX_FAILURES = 10
_LOCK = threading.Lock()
_FAILURES: dict[str, list[float]] = {}


def _now(value: float | None = None) -> float:
    return time.monotonic() if value is None else float(value)


def _prune(key: str, now: float) -> list[float]:
    cutoff = now - _WINDOW_SECONDS
    values = [stamp for stamp in _FAILURES.get(key, []) if stamp > cutoff]
    if values:
        _FAILURES[key] = values
    else:
        _FAILURES.pop(key, None)
    return values


def login_allowed(key: str, *, now: float | None = None) -> bool:
    stamp = _now(now)
    with _LOCK:
        return len(_prune(key, stamp)) < _MAX_FAILURES


def record_login_failure(key: str, *, now: float | None = None) -> int:
    stamp = _now(now)
    with _LOCK:
        values = _prune(key, stamp)
        values.append(stamp)
        _FAILURES[key] = values
        return len(values)


def clear_login_failures(key: str) -> None:
    with _LOCK:
        _FAILURES.pop(key, None)


def reset_login_guard_for_tests() -> None:
    with _LOCK:
        _FAILURES.clear()

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class CircuitState:
    consecutive_failures: int = 0
    opened_until: datetime | None = None
    last_failure_at: datetime | None = None
    last_success_at: datetime | None = None


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 5, recovery_seconds: int = 300) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_seconds < 1:
            raise ValueError("recovery_seconds must be >= 1")
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.state = CircuitState()
        self._lock = threading.RLock()

    def allow_request(self, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            if self.state.opened_until is None:
                return True
            if current >= self.state.opened_until:
                self.state.opened_until = None
                return True
            return False

    def record_success(self, *, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            self.state.consecutive_failures = 0
            self.state.opened_until = None
            self.state.last_success_at = current

    def record_failure(self, *, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            self.state.consecutive_failures += 1
            self.state.last_failure_at = current
            if self.state.consecutive_failures >= self.failure_threshold:
                self.state.opened_until = current + timedelta(seconds=self.recovery_seconds)

    def snapshot(self, *, now: datetime | None = None) -> dict[str, object]:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            opened_until = self.state.opened_until
            is_open = bool(opened_until and current < opened_until)
            return {
                "failure_threshold": self.failure_threshold,
                "recovery_seconds": self.recovery_seconds,
                "consecutive_failures": self.state.consecutive_failures,
                "open": is_open,
                "opened_until": opened_until.isoformat() if opened_until else None,
                "last_failure_at": self.state.last_failure_at.isoformat() if self.state.last_failure_at else None,
                "last_success_at": self.state.last_success_at.isoformat() if self.state.last_success_at else None,
            }


_LOCK = threading.RLock()
_REGISTRY: dict[str, CircuitBreaker] = {}


def for_source(source_id: str) -> CircuitBreaker:
    key = source_id.strip()
    if not key:
        raise ValueError("source_id is required")
    with _LOCK:
        breaker = _REGISTRY.get(key)
        if breaker is None:
            breaker = CircuitBreaker()
            _REGISTRY[key] = breaker
        return breaker


def reset_all() -> None:
    with _LOCK:
        _REGISTRY.clear()

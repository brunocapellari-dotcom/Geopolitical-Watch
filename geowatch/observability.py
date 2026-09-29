from __future__ import annotations

import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterator


@dataclass(frozen=True)
class TraceRecord:
    trace_id: str
    name: str
    started_at: str
    finished_at: str
    duration_ms: float
    status: str
    attributes: dict[str, object]
    error_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_LOCK = threading.RLock()
_RECENT: list[TraceRecord] = []
_TRACER = None


def _append(record: TraceRecord) -> None:
    with _LOCK:
        _RECENT.append(record)
        del _RECENT[:-200]


def recent_traces() -> list[dict[str, object]]:
    with _LOCK:
        return [row.to_dict() for row in _RECENT]


def _otel_tracer():
    global _TRACER
    if _TRACER is not None:
        return _TRACER
    endpoint = os.environ.get("GEOWATCH_PHOENIX_ENDPOINT", "").strip()
    if not endpoint:
        return None
    try:
        from opentelemetry import trace as otel_trace  # type: ignore
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
    except ImportError:
        return None
    provider = TracerProvider(resource=Resource.create({"service.name": "geopolitical-watch"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    otel_trace.set_tracer_provider(provider)
    _TRACER = otel_trace.get_tracer("geowatch")
    return _TRACER


@contextmanager
def trace(name: str, *, attributes: dict[str, object] | None = None) -> Iterator[str]:
    attrs = dict(attributes or {})
    trace_id = "trace_" + uuid.uuid4().hex
    started_wall = datetime.now(timezone.utc)
    started = time.perf_counter()
    status = "ok"
    error_type: str | None = None
    tracer = _otel_tracer()
    span = tracer.start_span(name) if tracer is not None else None
    if span is not None:
        for key, value in attrs.items():
            if isinstance(value, (str, bool, int, float)):
                span.set_attribute(str(key), value)
        span.set_attribute("geowatch.trace_id", trace_id)
    try:
        yield trace_id
    except Exception as exc:
        status = "error"
        error_type = type(exc).__name__
        if span is not None:
            span.record_exception(exc)
        raise
    finally:
        if span is not None:
            span.end()
        finished_wall = datetime.now(timezone.utc)
        record = TraceRecord(
            trace_id=trace_id,
            name=name,
            started_at=started_wall.isoformat(),
            finished_at=finished_wall.isoformat(),
            duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
            status=status,
            attributes=attrs,
            error_type=error_type,
        )
        _append(record)

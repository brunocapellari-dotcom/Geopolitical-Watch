from __future__ import annotations

import asyncio
import json
import os
import random
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .tracking_history import TrackHistory

_CONFIG_PATH = Path("config/operations/aisstream.json")
_LOCK = threading.RLock()
_THREAD: threading.Thread | None = None
_STATE: dict[str, object] = {
    "running": False,
    "connected": False,
    "started_at": None,
    "last_message_at": None,
    "last_message_epoch": None,
    "last_error": None,
    "reconnect_count": 0,
}
_VESSELS: dict[str, dict] = {}
_POSITION_TYPES = {"PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"}
_MMSI = re.compile(r"^\d{9}$")
_TRACKS = TrackHistory(
    max_entities=10000,
    max_points_per_entity=240,
    min_interval_seconds=5.0,
    min_move_meters=25.0,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _config() -> dict:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def _api_key() -> str | None:
    value = os.environ.get("AISSTREAM_API_KEY", "").strip()
    return value or None


def _stream_freshness(state: dict[str, object], stale_after: int) -> tuple[float | None, bool]:
    value = state.get("last_message_epoch")
    try:
        epoch = float(value) if value is not None else None
    except (TypeError, ValueError):
        epoch = None
    if epoch is None:
        return None, False
    age = max(0.0, time.time() - epoch)
    return round(age, 1), bool(state.get("connected")) and age <= stale_after


def provider_status() -> dict:
    cfg = _config()
    stale_after = int(cfg.get("stale_after_seconds", 900))
    with _LOCK:
        state = dict(_STATE)
        count = len(_VESSELS)
    stream_age, stream_fresh = _stream_freshness(state, stale_after)
    return {
        "schema_version": "geowatch-live-vessels-status-v2",
        "provider": "AISStream",
        "configured": bool(_api_key()),
        "regions": len(cfg.get("regions", [])),
        "coverage_semantics": cfg.get("coverage_semantics"),
        "vessel_count": count,
        "tracked_vessel_count": _TRACKS.entity_count(),
        "stream_age_seconds": stream_age,
        "stream_fresh": stream_fresh,
        **state,
    }


def ensure_started() -> bool:
    global _THREAD
    if not _api_key():
        return False
    with _LOCK:
        if _THREAD and _THREAD.is_alive():
            return True
        _THREAD = threading.Thread(target=_thread_main, name="geowatch-aisstream", daemon=True)
        _THREAD.start()
        return True


def _coord(value: object, *, minimum: float, maximum: float, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if number < minimum or number > maximum:
        raise ValueError(f"{name} out of range")
    return number


def _limit(value: object) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid limit") from exc
    if number < 1 or number > 5000:
        raise ValueError("limit out of range")
    return number


def _track_limit(value: object) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid limit") from exc
    if number < 2 or number > 240:
        raise ValueError("limit out of range")
    return number


def vessel_snapshot(
    *,
    south: object | None = None,
    west: object | None = None,
    north: object | None = None,
    east: object | None = None,
    limit: object = 1500,
) -> dict:
    ensure_started()
    cfg = _config()
    stale_after = int(cfg.get("stale_after_seconds", 900))
    track_retention = int(cfg.get("track_retention_seconds", 21600))
    result_limit = _limit(limit)
    bbox_requested = any(value is not None for value in (south, west, north, east))
    bbox: tuple[float, float, float, float] | None = None
    if bbox_requested:
        if any(value is None for value in (south, west, north, east)):
            raise ValueError("south, west, north and east are required together")
        s = _coord(south, minimum=-90, maximum=90, name="south")
        w = _coord(west, minimum=-180, maximum=180, name="west")
        n = _coord(north, minimum=-90, maximum=90, name="north")
        e = _coord(east, minimum=-180, maximum=180, name="east")
        if s > n:
            raise ValueError("south must be <= north")
        bbox = (s, w, n, e)

    now = time.time()
    with _LOCK:
        stale: list[str] = []
        for mmsi, row in _VESSELS.items():
            position_epoch = row.get("position_received_epoch")
            received_epoch = row.get("received_epoch")
            try:
                reference_epoch = float(position_epoch if position_epoch is not None else received_epoch or 0)
            except (TypeError, ValueError):
                reference_epoch = 0.0
            if now - reference_epoch > stale_after:
                stale.append(mmsi)
        for mmsi in stale:
            _VESSELS.pop(mmsi, None)
        active_rows = [dict(row) for row in _VESSELS.values() if row.get("position_received_epoch") is not None]
        active_total = len(active_rows)
        state = dict(_STATE)

    vessels: list[dict] = []
    for row in active_rows:
        try:
            position_age = max(0.0, now - float(row["position_received_epoch"]))
        except (TypeError, ValueError, KeyError):
            continue
        vessels.append({**row, "position_age_seconds": round(position_age, 1)})

    if bbox is not None:
        s, w, n, e = bbox
        filtered: list[dict] = []
        for row in vessels:
            try:
                lat = float(row.get("lat"))
                lon = float(row.get("lon"))
            except (TypeError, ValueError):
                continue
            if not (s <= lat <= n):
                continue
            longitude_matches = w <= lon <= e if w <= e else lon >= w or lon <= e
            if longitude_matches:
                filtered.append(row)
        vessels = filtered

    vessels.sort(key=lambda row: str(row.get("ship_name") or row.get("mmsi") or ""))
    truncated = len(vessels) > result_limit
    vessels = vessels[:result_limit]
    _TRACKS.prune(older_than_seconds=track_retention, now_epoch=now)
    stream_age, stream_fresh = _stream_freshness(state, stale_after)
    return {
        "schema_version": "geowatch-live-vessels-v2",
        "provider": "AISStream",
        "configured": bool(_api_key()),
        "coverage_semantics": cfg.get("coverage_semantics"),
        "observed_at": _utc_now(),
        "active_total": active_total,
        "count": len(vessels),
        "truncated": truncated,
        "stream_age_seconds": stream_age,
        "stream_fresh": stream_fresh,
        "bbox": {"south": bbox[0], "west": bbox[1], "north": bbox[2], "east": bbox[3]} if bbox else None,
        "vessels": vessels,
        "collector": state,
    }


def vessel_track(mmsi: object, *, limit: object = 240) -> dict:
    key = str(mmsi or "").strip()
    if not _MMSI.fullmatch(key):
        raise ValueError("invalid mmsi")
    result_limit = _track_limit(limit)
    cfg = _config()
    _TRACKS.prune(older_than_seconds=int(cfg.get("track_retention_seconds", 21600)))
    points = _TRACKS.get(key, limit=result_limit)
    return {
        "schema_version": "geowatch-vessel-track-v1",
        "provider": "AISStream",
        "mmsi": key,
        "count": len(points),
        "points": points,
        "track_semantics": (
            "recent observed AIS positions collected by this running backend; "
            "not a complete voyage, historical port-call record, or inferred origin/destination"
        ),
    }


def _thread_main() -> None:
    with _LOCK:
        _STATE.update({"running": True, "started_at": _utc_now(), "last_error": None})
    try:
        asyncio.run(_run_forever())
    except Exception as exc:
        with _LOCK:
            _STATE.update({"running": False, "connected": False, "last_error": f"{type(exc).__name__}: {exc}"})


async def _run_forever() -> None:
    cfg = _config()
    endpoint = str(cfg.get("endpoint") or "wss://stream.aisstream.io/v0/stream")
    regions = list(cfg.get("regions") or [])
    boxes = [row.get("box") for row in regions if isinstance(row, dict) and row.get("box")]
    message_types = list(cfg.get("message_types") or ["PositionReport"])
    max_vessels = int(cfg.get("max_vessels", 10000))
    backoff = 1.0

    while True:
        key = _api_key()
        if not key:
            with _LOCK:
                _STATE.update({"connected": False, "last_error": "AISSTREAM_API_KEY missing"})
            await asyncio.sleep(30)
            continue
        try:
            import websockets

            async with websockets.connect(
                endpoint,
                compression="deflate",
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
                max_size=2 * 1024 * 1024,
            ) as ws:
                await ws.send(json.dumps({
                    "APIKey": key,
                    "BoundingBoxes": boxes,
                    "FilterMessageTypes": message_types,
                }))
                with _LOCK:
                    _STATE.update({"connected": True, "last_error": None})
                backoff = 1.0
                async for raw in ws:
                    _consume(raw, max_vessels=max_vessels)
        except Exception as exc:
            with _LOCK:
                _STATE["connected"] = False
                _STATE["last_error"] = f"{type(exc).__name__}: {exc}"
                _STATE["reconnect_count"] = int(_STATE.get("reconnect_count") or 0) + 1
            await asyncio.sleep(backoff + random.random() * min(backoff, 2.0))
            backoff = min(backoff * 2.0, 60.0)


def _eta_fragment(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    try:
        month = int(value.get("Month") or 0)
        day = int(value.get("Day") or 0)
        hour = int(value.get("Hour") or 0)
        minute = int(value.get("Minute") or 0)
    except (TypeError, ValueError):
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{month:02d}-{day:02d} {hour:02d}:{minute:02d} UTC (ano não transmitido pelo AIS)"


def _static_fields(message_type: str, message: dict) -> dict[str, object]:
    if message_type == "ShipStaticData":
        return {
            "ship_name": str(message.get("Name") or "").strip() or None,
            "imo_number": message.get("ImoNumber"),
            "call_sign": str(message.get("CallSign") or "").strip() or None,
            "ship_type_code": message.get("Type"),
            "reported_destination": str(message.get("Destination") or "").strip() or None,
            "reported_eta": _eta_fragment(message.get("Eta")),
            "maximum_static_draught_m": message.get("MaximumStaticDraught"),
        }
    if message_type == "StaticDataReport":
        report_a = message.get("ReportA") if isinstance(message.get("ReportA"), dict) else {}
        report_b = message.get("ReportB") if isinstance(message.get("ReportB"), dict) else {}
        return {
            "ship_name": str(report_a.get("Name") or "").strip() or None,
            "call_sign": str(report_b.get("CallSign") or "").strip() or None,
            "ship_type_code": report_b.get("ShipType"),
        }
    return {}


def _consume(raw: object, *, max_vessels: int) -> None:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        event = json.loads(str(raw))
    except json.JSONDecodeError:
        return
    if not isinstance(event, dict):
        return
    message_type = str(event.get("MessageType") or "")
    now_epoch = time.time()
    now_iso = _utc_now()
    if message_type == "SubscriptionConfirmation":
        with _LOCK:
            _STATE.update({"last_message_at": now_iso, "last_message_epoch": now_epoch})
        return

    meta = event.get("MetaData") if isinstance(event.get("MetaData"), dict) else {}
    mmsi = str(meta.get("MMSI") or "").strip()
    if not mmsi:
        return
    message_container = event.get("Message") if isinstance(event.get("Message"), dict) else {}
    message = message_container.get(message_type) if isinstance(message_container.get(message_type), dict) else {}
    is_position = message_type in _POSITION_TYPES

    row: dict[str, object] = {
        "mmsi": mmsi,
        "ship_name": str(meta.get("ShipName") or "").strip() or None,
        "message_type": message_type,
        "received_at": now_iso,
        "received_epoch": now_epoch,
        "ais_semantics": "reported/observed AIS data; reported destination/ETA are vessel-declared and not verified voyage intent",
        **_static_fields(message_type, message),
    }
    if is_position:
        row.update({
            "lat": meta.get("Latitude"),
            "lon": meta.get("Longitude"),
            "speed_over_ground_kt": message.get("Sog"),
            "course_over_ground_deg": message.get("Cog"),
            "true_heading_deg": message.get("TrueHeading"),
            "navigational_status": message.get("NavigationalStatus"),
            "position_received_at": now_iso,
            "position_received_epoch": now_epoch,
        })

    with _LOCK:
        previous = _VESSELS.get(mmsi, {})
        merged = {**previous, **{key: value for key, value in row.items() if value is not None}}
        _VESSELS[mmsi] = merged
        if len(_VESSELS) > max_vessels:
            oldest = sorted(_VESSELS.items(), key=lambda item: float(item[1].get("received_epoch", 0)))[: len(_VESSELS) - max_vessels]
            for key, _ in oldest:
                _VESSELS.pop(key, None)
        _STATE.update({"last_message_at": now_iso, "last_message_epoch": now_epoch})

    if is_position:
        try:
            _TRACKS.record(
                mmsi,
                row.get("lat"),
                row.get("lon"),
                observed_at=now_iso,
                epoch=now_epoch,
                properties={
                    "speed_over_ground_kt": row.get("speed_over_ground_kt"),
                    "course_over_ground_deg": row.get("course_over_ground_deg"),
                },
            )
        except ValueError:
            pass


def reset_for_tests() -> None:
    global _THREAD
    with _LOCK:
        _VESSELS.clear()
        _STATE.update({
            "running": False,
            "connected": False,
            "started_at": None,
            "last_message_at": None,
            "last_message_epoch": None,
            "last_error": None,
            "reconnect_count": 0,
        })
        _THREAD = None
    _TRACKS.clear()

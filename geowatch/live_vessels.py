from __future__ import annotations

import asyncio
import json
import os
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_CONFIG_PATH = Path("config/operations/aisstream.json")
_LOCK = threading.RLock()
_THREAD: threading.Thread | None = None
_STATE: dict[str, object] = {
    "running": False,
    "connected": False,
    "started_at": None,
    "last_message_at": None,
    "last_error": None,
    "reconnect_count": 0,
}
_VESSELS: dict[str, dict] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _config() -> dict:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def _api_key() -> str | None:
    value = os.environ.get("AISSTREAM_API_KEY", "").strip()
    return value or None


def provider_status() -> dict:
    cfg = _config()
    with _LOCK:
        state = dict(_STATE)
        count = len(_VESSELS)
    return {
        "schema_version": "geowatch-live-vessels-status-v1",
        "provider": "AISStream",
        "configured": bool(_api_key()),
        "regions": len(cfg.get("regions", [])),
        "coverage_semantics": cfg.get("coverage_semantics"),
        "vessel_count": count,
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


def vessel_snapshot() -> dict:
    ensure_started()
    cfg = _config()
    stale_after = int(cfg.get("stale_after_seconds", 900))
    now = time.time()
    with _LOCK:
        stale = [mmsi for mmsi, row in _VESSELS.items() if now - float(row.get("received_epoch", 0)) > stale_after]
        for mmsi in stale:
            _VESSELS.pop(mmsi, None)
        vessels = [dict(row) for row in _VESSELS.values()]
        state = dict(_STATE)
    vessels.sort(key=lambda row: str(row.get("ship_name") or row.get("mmsi") or ""))
    return {
        "schema_version": "geowatch-live-vessels-v1",
        "provider": "AISStream",
        "configured": bool(_api_key()),
        "coverage_semantics": cfg.get("coverage_semantics"),
        "observed_at": _utc_now(),
        "count": len(vessels),
        "vessels": vessels,
        "collector": state,
    }


def _thread_main() -> None:
    with _LOCK:
        _STATE.update({"running": True, "started_at": _utc_now(), "last_error": None})
    try:
        asyncio.run(_run_forever())
    except Exception as exc:  # defensive outer guard; daemon must never crash the API process
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
                subscription = {
                    "APIKey": key,
                    "BoundingBoxes": boxes,
                    "FilterMessageTypes": message_types,
                }
                await ws.send(json.dumps(subscription))
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
    if message_type == "SubscriptionConfirmation":
        with _LOCK:
            _STATE["last_message_at"] = _utc_now()
        return

    meta = event.get("MetaData") if isinstance(event.get("MetaData"), dict) else {}
    mmsi = str(meta.get("MMSI") or "").strip()
    if not mmsi:
        return
    message_container = event.get("Message") if isinstance(event.get("Message"), dict) else {}
    message = message_container.get(message_type) if isinstance(message_container.get(message_type), dict) else {}
    now_epoch = time.time()
    row = {
        "mmsi": mmsi,
        "ship_name": str(meta.get("ShipName") or "").strip() or None,
        "lat": meta.get("Latitude"),
        "lon": meta.get("Longitude"),
        "speed_over_ground_kt": message.get("Sog"),
        "course_over_ground_deg": message.get("Cog"),
        "true_heading_deg": message.get("TrueHeading"),
        "navigational_status": message.get("NavigationalStatus"),
        "message_type": message_type,
        "received_at": _utc_now(),
        "received_epoch": now_epoch,
        "ais_semantics": "reported/observed AIS data; not verified voyage intent",
    }
    with _LOCK:
        previous = _VESSELS.get(mmsi, {})
        merged = {**previous, **{key: value for key, value in row.items() if value is not None}}
        _VESSELS[mmsi] = merged
        if len(_VESSELS) > max_vessels:
            oldest = sorted(_VESSELS.items(), key=lambda item: float(item[1].get("received_epoch", 0)))[: len(_VESSELS) - max_vessels]
            for key, _ in oldest:
                _VESSELS.pop(key, None)
        _STATE["last_message_at"] = row["received_at"]


def reset_for_tests() -> None:
    global _THREAD
    with _LOCK:
        _VESSELS.clear()
        _STATE.update({
            "running": False,
            "connected": False,
            "started_at": None,
            "last_message_at": None,
            "last_error": None,
            "reconnect_count": 0,
        })
        _THREAD = None

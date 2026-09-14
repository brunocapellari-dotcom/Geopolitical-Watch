from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timezone

from .http import get

_BASE = "https://api.adsb.lol"
_CACHE_TTL_SECONDS = 20.0
_ROUTE_CACHE_TTL_SECONDS = 300.0
_CALLSIGN = re.compile(r"^[A-Z0-9]{2,16}$")
_CACHE: dict[tuple, tuple[float, dict]] = {}
_LOCK = threading.RLock()


class LiveAircraftError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_float(value: object, *, minimum: float, maximum: float, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if number < minimum or number > maximum:
        raise ValueError(f"{name} out of range")
    return number


def _bounded_int(value: object, *, minimum: int, maximum: int, name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if number < minimum or number > maximum:
        raise ValueError(f"{name} out of range")
    return number


def _cached(key: tuple) -> dict | None:
    now = time.monotonic()
    with _LOCK:
        row = _CACHE.get(key)
        if not row:
            return None
        expires_at, payload = row
        if expires_at < now:
            _CACHE.pop(key, None)
            return None
        return payload


def _store(key: tuple, payload: dict, ttl: float) -> dict:
    with _LOCK:
        _CACHE[key] = (time.monotonic() + ttl, payload)
    return payload


def _json_payload(url: str, *, timeout: int = 12) -> dict:
    try:
        response = get(url, timeout=timeout, retries=1, backoff_seconds=0.5, max_backoff_seconds=2.0)
        body = json.loads(response.payload.decode("utf-8"))
    except Exception as exc:  # provider failure is isolated from the main API
        raise LiveAircraftError(f"aircraft provider unavailable: {type(exc).__name__}") from exc
    if not isinstance(body, dict):
        raise LiveAircraftError("aircraft provider returned invalid payload")
    return body


def aircraft_snapshot(lat: object, lon: object, dist_nm: object = 150) -> dict:
    latitude = _bounded_float(lat, minimum=-90.0, maximum=90.0, name="lat")
    longitude = _bounded_float(lon, minimum=-180.0, maximum=180.0, name="lon")
    distance = _bounded_int(dist_nm, minimum=1, maximum=250, name="dist_nm")
    key = ("aircraft", round(latitude, 2), round(longitude, 2), distance)
    cached = _cached(key)
    if cached is not None:
        return {**cached, "cache_hit": True}

    body = _json_payload(f"{_BASE}/v2/lat/{latitude:.4f}/lon/{longitude:.4f}/dist/{distance}")
    aircraft = []
    compact = []
    for row in body.get("ac", []):
        if not isinstance(row, dict):
            continue
        if row.get("lat") is None or row.get("lon") is None:
            continue
        normalized = {
            "hex": row.get("hex"),
            "flight": row.get("flight"),
            "registration": row.get("r"),
            "aircraft_type": row.get("t"),
            "lat": row.get("lat"),
            "lon": row.get("lon"),
            "altitude_baro_ft": row.get("alt_baro"),
            "ground_speed_kt": row.get("gs"),
            "track_deg": row.get("track"),
            "vertical_rate_fpm": row.get("baro_rate"),
            "squawk": row.get("squawk"),
            "seen_seconds": row.get("seen"),
            "category": row.get("category"),
        }
        aircraft.append(normalized)
        compact.append({
            "hex": normalized["hex"], "flight": normalized["flight"],
            "r": normalized["registration"], "t": normalized["aircraft_type"],
            "lat": normalized["lat"], "lon": normalized["lon"],
            "alt_baro": normalized["altitude_baro_ft"], "gs": normalized["ground_speed_kt"],
            "track": normalized["track_deg"], "baro_rate": normalized["vertical_rate_fpm"],
            "squawk": normalized["squawk"], "seen": normalized["seen_seconds"],
            "category": normalized["category"],
        })
    payload = {
        "schema_version": "geowatch-live-aircraft-v1",
        "provider": "adsb.lol",
        "provider_semantics": "public ADS-B/MLAT observation; coverage and completeness vary",
        "observed_at": _utc_now(),
        "center": {"lat": latitude, "lon": longitude, "radius_nm": distance},
        "count": len(aircraft),
        "aircraft": aircraft,
        "ac": compact,
        "cache_hit": False,
    }
    return _store(key, payload, _CACHE_TTL_SECONDS)


def aircraft_route(callsign: object, lat: object, lon: object) -> dict:
    cs = str(callsign or "").strip().upper()
    if not _CALLSIGN.fullmatch(cs):
        raise ValueError("invalid callsign")
    latitude = _bounded_float(lat, minimum=-90.0, maximum=90.0, name="lat")
    longitude = _bounded_float(lon, minimum=-180.0, maximum=180.0, name="lon")
    key = ("route", cs, round(latitude, 2), round(longitude, 2))
    cached = _cached(key)
    if cached is not None:
        return {**cached, "cache_hit": True}

    body = _json_payload(f"{_BASE}/api/0/route/{cs}/{latitude:.4f}/{longitude:.4f}")
    airports = []
    for row in body.get("_airports", []):
        if not isinstance(row, dict):
            continue
        airports.append({
            "icao": row.get("icao"),
            "iata": row.get("iata"),
            "name": row.get("name"),
            "lat": row.get("lat"),
            "lon": row.get("lon"),
        })
    payload = {
        "schema_version": "geowatch-aircraft-route-v1",
        "provider": "adsb.lol/VRS standing data",
        "callsign": cs,
        "airport_codes": body.get("airport_codes"),
        "plausible": body.get("plausible"),
        "route_semantics": "route lookup is inferred/plausibility-checked context, not a confirmed filed flight plan",
        "airports": airports,
        "_airports": airports,
        "observed_at": _utc_now(),
        "cache_hit": False,
    }
    return _store(key, payload, _ROUTE_CACHE_TTL_SECONDS)


def clear_live_aircraft_cache() -> None:
    with _LOCK:
        _CACHE.clear()

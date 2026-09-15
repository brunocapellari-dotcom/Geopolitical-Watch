from __future__ import annotations

import math
import threading
import time
from collections import deque
from datetime import datetime, timezone


class TrackHistory:
    """Thread-safe bounded in-memory position history.

    This store is intentionally source-agnostic so aircraft and vessel tracking
    share one implementation. It is a recent operational trail, not a complete
    historical route and not evidence of intent.
    """

    def __init__(
        self,
        *,
        max_entities: int,
        max_points_per_entity: int,
        min_interval_seconds: float = 2.0,
        min_move_meters: float = 15.0,
    ) -> None:
        if max_entities < 1 or max_points_per_entity < 2:
            raise ValueError("track history bounds must be positive")
        self.max_entities = int(max_entities)
        self.max_points_per_entity = int(max_points_per_entity)
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.min_move_meters = max(0.0, float(min_move_meters))
        self._tracks: dict[str, deque[dict[str, object]]] = {}
        self._last_touch: dict[str, float] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _coord(value: object, *, minimum: float, maximum: float, name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid {name}") from exc
        if not math.isfinite(number) or number < minimum or number > maximum:
            raise ValueError(f"{name} out of range")
        return number

    @staticmethod
    def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6_371_008.8
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * radius * math.asin(min(1.0, math.sqrt(a)))

    def record(
        self,
        entity_id: object,
        lat: object,
        lon: object,
        *,
        observed_at: str | None = None,
        epoch: float | None = None,
        properties: dict[str, object] | None = None,
    ) -> bool:
        key = str(entity_id or "").strip()
        if not key or len(key) > 64:
            raise ValueError("invalid entity_id")
        latitude = self._coord(lat, minimum=-90.0, maximum=90.0, name="lat")
        longitude = self._coord(lon, minimum=-180.0, maximum=180.0, name="lon")
        ts = float(time.time() if epoch is None else epoch)
        if not math.isfinite(ts) or ts < 0:
            raise ValueError("invalid epoch")
        stamp = observed_at or datetime.fromtimestamp(ts, timezone.utc).isoformat()

        with self._lock:
            track = self._tracks.get(key)
            if track:
                previous = track[-1]
                previous_epoch = float(previous["epoch"])
                distance = self._distance_meters(
                    float(previous["lat"]), float(previous["lon"]), latitude, longitude
                )
                if ts <= previous_epoch:
                    return False
                if ts - previous_epoch < self.min_interval_seconds and distance < self.min_move_meters:
                    return False
                if distance < self.min_move_meters:
                    self._last_touch[key] = ts
                    return False
            else:
                track = deque(maxlen=self.max_points_per_entity)
                self._tracks[key] = track

            point: dict[str, object] = {
                "lat": latitude,
                "lon": longitude,
                "observed_at": stamp,
                "epoch": ts,
            }
            if properties:
                for name, value in properties.items():
                    if value is not None and name not in point:
                        point[name] = value
            track.append(point)
            self._last_touch[key] = ts
            self._evict_if_needed()
            return True

    def _evict_if_needed(self) -> None:
        overflow = len(self._tracks) - self.max_entities
        if overflow <= 0:
            return
        for key, _ in sorted(self._last_touch.items(), key=lambda item: item[1])[:overflow]:
            self._tracks.pop(key, None)
            self._last_touch.pop(key, None)

    def get(self, entity_id: object, *, limit: object | None = None) -> list[dict[str, object]]:
        key = str(entity_id or "").strip()
        if not key or len(key) > 64:
            raise ValueError("invalid entity_id")
        if limit is None:
            result_limit = self.max_points_per_entity
        else:
            try:
                result_limit = int(limit)
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid limit") from exc
            if result_limit < 2 or result_limit > self.max_points_per_entity:
                raise ValueError("limit out of range")
        with self._lock:
            rows = list(self._tracks.get(key, ()))
        return [dict(row) for row in rows[-result_limit:]]

    def prune(self, *, older_than_seconds: float, now_epoch: float | None = None) -> int:
        max_age = max(1.0, float(older_than_seconds))
        now = float(time.time() if now_epoch is None else now_epoch)
        with self._lock:
            stale = [key for key, touched in self._last_touch.items() if now - touched > max_age]
            for key in stale:
                self._tracks.pop(key, None)
                self._last_touch.pop(key, None)
            return len(stale)

    def clear(self) -> None:
        with self._lock:
            self._tracks.clear()
            self._last_touch.clear()

    def entity_count(self) -> int:
        with self._lock:
            return len(self._tracks)

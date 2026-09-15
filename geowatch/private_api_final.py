from __future__ import annotations

import os
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .api import API_TOKEN, Handler as BaseHandler
from .collector_scheduler import ensure_started as ensure_source_scheduler_started
from .embedded_collector import ensure_started as ensure_collector_started
from .live_aircraft import aircraft_track
from .live_vessels import ensure_started as ensure_vessel_started, vessel_track
from .private_api import PrivateHandler as CorePrivateHandler, _flag
from .runtime_guard import validate_production_runtime
from .web_auth import verify_session


def _secure_cookie() -> bool:
    value = os.environ.get("GEOWATCH_COOKIE_SECURE", "1").strip().casefold()
    return value not in {"0", "false", "no", "off"}


def _one(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


class PrivateHandler(CorePrivateHandler):
    """Final HTTP handler with a MapLibre-compatible restrictive CSP."""

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com; "
            "img-src 'self' data: blob: https://unpkg.com https://*.tile.openstreetmap.org https://storage.googleapis.com; "
            "connect-src 'self' https://unpkg.com https://*.tile.openstreetmap.org https://storage.googleapis.com; "
            "worker-src 'self' blob:; child-src 'self' blob:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )
        if _secure_cookie():
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        BaseHandler.end_headers(self)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path not in {"/v2/live/aircraft/track", "/v2/live/vessels/track"}:
            return super().do_GET()

        session_ok = verify_session(self.headers.get("Cookie"), API_TOKEN)
        bearer_ok = (not API_TOKEN) or self.headers.get("Authorization") == f"Bearer {API_TOKEN}"
        if not (session_ok or bearer_ok):
            return self._send_json(401, {"error": "unauthorized"})

        query = parse_qs(parsed.query)
        try:
            if path == "/v2/live/aircraft/track":
                return self._send_json(200, aircraft_track(_one(query, "hex"), limit=_one(query, "limit") or 120))
            return self._send_json(200, vessel_track(_one(query, "mmsi"), limit=_one(query, "limit") or 240))
        except ValueError as exc:
            return self._send_json(400, {"error": str(exc)})


def main() -> int:
    validate_production_runtime()
    if _flag("GEOWATCH_SOURCE_SCHEDULER"):
        ensure_source_scheduler_started()
    elif _flag("GEOWATCH_EMBEDDED_COLLECTOR"):
        ensure_collector_started()
    # GEOWATCH_EXTERNAL_SCHEDULER deliberately starts no batch-collection thread.
    # Cloud Scheduler invokes a one-shot Cloud Run Job instead.
    ensure_vessel_started()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), PrivateHandler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

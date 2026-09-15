from __future__ import annotations

import os
from http.server import ThreadingHTTPServer

from .api import Handler as BaseHandler
from .collector_scheduler import ensure_started as ensure_source_scheduler_started
from .embedded_collector import ensure_started as ensure_collector_started
from .live_vessels import ensure_started as ensure_vessel_started
from .private_api import PrivateHandler as CorePrivateHandler, _flag
from .runtime_guard import validate_production_runtime


def _secure_cookie() -> bool:
    value = os.environ.get("GEOWATCH_COOKIE_SECURE", "1").strip().casefold()
    return value not in {"0", "false", "no", "off"}


class PrivateHandler(CorePrivateHandler):
    """Final HTTP handler.

    The core routes stay in ``private_api.PrivateHandler``. This final handler only
    owns browser security headers so the MapLibre Web Worker can run without
    relaxing script execution to arbitrary origins.
    """

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
        # Bypass CorePrivateHandler.end_headers so an older, more restrictive CSP
        # is not emitted in parallel and combined by the browser.
        BaseHandler.end_headers(self)


def main() -> int:
    validate_production_runtime()
    if _flag("GEOWATCH_SOURCE_SCHEDULER"):
        ensure_source_scheduler_started()
    else:
        ensure_collector_started()
    ensure_vessel_started()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), PrivateHandler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

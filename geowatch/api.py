from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .reports import build_feed
from .storage import SQLiteStore

DB_PATH = os.environ.get("GEOWATCH_DB", "data/geowatch.db")
API_TOKEN = os.environ.get("GEOWATCH_API_TOKEN")


class Handler(BaseHTTPRequestHandler):
    server_version = "GeopoliticalWatch/0.4"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            return self._send(200, {"status": "ok", "service": "geopolitical-watch", "version": "0.4.0"})
        if API_TOKEN and self.headers.get("Authorization") != f"Bearer {API_TOKEN}":
            return self._send(401, {"error": "unauthorized"})
        store = SQLiteStore(DB_PATH)
        report = store.latest_report("situational")
        store.close()
        if report is None:
            return self._send(404, {"error": "no report available"})
        if path == "/v1/reports/latest":
            return self._send(200, report)
        if path == "/v1/feed":
            return self._send(200, build_feed(report))
        return self._send(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:
        return

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

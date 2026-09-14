from __future__ import annotations

import os
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

from .api import API_TOKEN, Handler as BaseHandler
from .web_auth import clear_cookie, login_html, session_cookie, verify_login_body, verify_session


def _secure_cookie() -> bool:
    value = os.environ.get("GEOWATCH_COOKIE_SECURE", "1").strip().casefold()
    return value not in {"0", "false", "no", "off"}


class PrivateHandler(BaseHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/login":
            if verify_session(self.headers.get("Cookie"), API_TOKEN):
                return self._redirect("/dashboard")
            return self._send_text(200, login_html(), "text/html; charset=utf-8")
        if path == "/logout":
            self.send_response(303)
            self.send_header("Location", "/login")
            self.send_header("Set-Cookie", clear_cookie(secure=_secure_cookie()))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        session_ok = verify_session(self.headers.get("Cookie"), API_TOKEN)
        if path == "/dashboard" and API_TOKEN and not session_ok:
            return self._send_text(200, login_html(), "text/html; charset=utf-8")

        # Same-origin browser sessions are translated to the existing Bearer
        # contract; machine clients can keep sending Authorization themselves.
        if session_ok and API_TOKEN and self.headers.get("Authorization") != f"Bearer {API_TOKEN}":
            if self.headers.get("Authorization"):
                self.headers.replace_header("Authorization", f"Bearer {API_TOKEN}")
            else:
                self.headers.add_header("Authorization", f"Bearer {API_TOKEN}")
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/login":
            return self._send_json(405, {"error": "method not allowed"})
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length < 0 or length > 4096:
            return self._send_json(413, {"error": "request too large"})
        body = self.rfile.read(length)
        if not verify_login_body(body, API_TOKEN):
            return self._send_text(401, login_html(invalid=True), "text/html; charset=utf-8")
        if not API_TOKEN:
            return self._redirect("/dashboard")
        self.send_response(303)
        self.send_header("Location", "/dashboard")
        self.send_header("Set-Cookie", session_cookie(API_TOKEN, secure=_secure_cookie()))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def main() -> int:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), PrivateHandler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

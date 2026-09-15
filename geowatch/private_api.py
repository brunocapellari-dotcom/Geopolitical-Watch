from __future__ import annotations

import os
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .ai_roles import load_ai_roles
from .api import API_TOKEN, Handler as BaseHandler
from .architecture_status import build_architecture_status
from .claim_verification import verify_claims
from .collector_scheduler import ensure_started as ensure_source_scheduler_started, status as source_scheduler_status
from .context_feed import build_context_feed
from .dashboard import dashboard_html
from .embedded_collector import ensure_started as ensure_collector_started, status as collector_status
from .live_vessels import ensure_started as ensure_vessel_started, vessel_snapshot
from .login_guard import clear_login_failures, login_allowed, record_login_failure
from .runtime_guard import validate_production_runtime
from .runtime_readiness import build_runtime_readiness
from .source_health import build_source_health
from .source_registry import load_registry
from .storage_factory import open_store
from .web_auth import clear_cookie, login_html, session_cookie, verify_login_body, verify_session


def _secure_cookie() -> bool:
    value = os.environ.get("GEOWATCH_COOKIE_SECURE", "1").strip().casefold()
    return value not in {"0", "false", "no", "off"}


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _private_dashboard_html() -> str:
    body = dashboard_html()
    body = body.replace(
        '<input id="token" type="password" placeholder="API bearer token">',
        '<input id="token" type="hidden" value=""><a href="/logout" style="color:#adb5bd;text-decoration:none;font-size:12px">Sair</a>',
    )
    return body


def _query_one(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


def _query_int(query: dict[str, list[str]], name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(_query_one(query, name) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


class PrivateHandler(BaseHandler):
    server_version = "GeopoliticalWatch"
    sys_version = ""

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com; "
            "img-src 'self' data: https://unpkg.com https://*.tile.openstreetmap.org; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )
        if _secure_cookie():
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        super().end_headers()

    def _login_key(self) -> str:
        try:
            return str(self.client_address[0])
        except (AttributeError, IndexError, TypeError):
            return "unknown"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if path == "/health":
            return self._send_json(200, {"status": "ok", "service": "geopolitical-watch"})
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
        bearer_ok = (not API_TOKEN) or self.headers.get("Authorization") == f"Bearer {API_TOKEN}"
        if path == "/dashboard":
            if API_TOKEN and not session_ok:
                return self._send_text(200, login_html(), "text/html; charset=utf-8")
            return self._send_text(200, _private_dashboard_html(), "text/html; charset=utf-8")

        private_runtime_paths = {
            "/v2/runtime/collector",
            "/v2/runtime/readiness",
            "/v2/runtime/source-scheduler",
            "/v2/source-health",
            "/v2/architecture/status",
            "/v2/architecture/sources",
            "/v2/architecture/ai-roles",
            "/v2/context/physical",
            "/v2/context/network",
            "/v2/verification/episode",
            "/v2/sanctions/summary",
            "/v2/satellite/catalog",
            "/v2/live/vessels",
        }
        if path in private_runtime_paths:
            if not (session_ok or bearer_ok):
                return self._send_json(401, {"error": "unauthorized"})
            if path == "/v2/runtime/collector":
                return self._send_json(200, collector_status())
            if path == "/v2/runtime/readiness":
                return self._send_json(200, build_runtime_readiness())
            if path == "/v2/runtime/source-scheduler":
                return self._send_json(200, source_scheduler_status())
            if path == "/v2/architecture/status":
                return self._send_json(200, build_architecture_status())
            if path == "/v2/architecture/sources":
                return self._send_json(200, load_registry().summary())
            if path == "/v2/architecture/ai-roles":
                return self._send_json(200, load_ai_roles().summary())
            if path in {"/v2/context/physical", "/v2/context/network", "/v2/verification/episode", "/v2/source-health", "/v2/sanctions/summary", "/v2/satellite/catalog"}:
                return self._data_view(path, query)
            try:
                return self._send_json(200, vessel_snapshot(
                    south=_query_one(query, "south"),
                    west=_query_one(query, "west"),
                    north=_query_one(query, "north"),
                    east=_query_one(query, "east"),
                    limit=_query_one(query, "limit") or 1500,
                ))
            except ValueError as exc:
                return self._send_json(400, {"error": str(exc)})

        if session_ok and API_TOKEN and not bearer_ok:
            if self.headers.get("Authorization"):
                self.headers.replace_header("Authorization", f"Bearer {API_TOKEN}")
            else:
                self.headers.add_header("Authorization", f"Bearer {API_TOKEN}")
        return super().do_GET()

    def _data_view(self, path: str, query: dict[str, list[str]]) -> None:
        store = open_store()
        try:
            if path == "/v2/source-health":
                return self._send_json(200, build_source_health(store))
            if path == "/v2/context/physical":
                return self._send_json(200, build_context_feed(
                    store,
                    source_ids={"usgs_earthquakes", "nasa_firms_context"},
                    hours=_query_int(query, "hours", 24, 1, 24 * 30),
                    limit=_query_int(query, "limit", 1000, 1, 5000),
                ))
            if path == "/v2/context/network":
                return self._send_json(200, build_context_feed(
                    store,
                    source_ids={"ioda_outages", "ripestat_bgp"},
                    hours=_query_int(query, "hours", 24, 1, 24 * 30),
                    limit=_query_int(query, "limit", 1000, 1, 5000),
                ))
            if path == "/v2/sanctions/summary":
                return self._send_json(200, self._sanctions_summary(store))
            if path == "/v2/satellite/catalog":
                report = store.latest_report("satellite_catalog_celestrak")
                if report is None:
                    return self._send_json(404, {"error": "satellite catalog not available"})
                limit = _query_int(query, "limit", 500, 1, 5000)
                satellites = list(report.get("satellites") or [])[:limit]
                return self._send_json(200, {
                    **{key: value for key, value in report.items() if key != "satellites"},
                    "returned_count": len(satellites),
                    "satellites": satellites,
                })
            episode_id = (_query_one(query, "episode_id") or "").strip()
            if not episode_id or len(episode_id) > 128:
                return self._send_json(400, {"error": "episode_id is required"})
            episode = store.get_episode(episode_id)
            if episode is None:
                return self._send_json(404, {"error": "episode not found"})
            claims = store.load_claims(episode_id=episode_id)
            evidence = store.load_evidence(episode_id=episode_id)
            events = store.load_events_by_ids(episode.event_ids)
            verdicts = verify_claims(claims, evidence=evidence, events=events)
            return self._send_json(200, {
                "schema_version": "geowatch-episode-verification-v1",
                "episode_id": episode_id,
                "verdicts": [verdicts[claim.claim_id].to_dict() for claim in claims if claim.claim_id in verdicts],
            })
        finally:
            store.close()

    @staticmethod
    def _sanctions_summary(store) -> dict[str, object]:
        authorities: dict[str, object] = {}
        for source_id in ("unsc_sanctions", "uk_sanctions"):
            report = store.latest_report(f"sanctions_snapshot_{source_id}")
            if report is None:
                authorities[source_id] = {"status": "not_available"}
                continue
            diff = report.get("diff") or {}
            authorities[source_id] = {
                "status": "available",
                "generated_at": report.get("generated_at"),
                "designation_count": report.get("designation_count"),
                "sha256": report.get("sha256"),
                "changes": {
                    "added": len(diff.get("added", [])) if isinstance(diff, dict) else 0,
                    "removed": len(diff.get("removed", [])) if isinstance(diff, dict) else 0,
                    "modified": len(diff.get("modified", [])) if isinstance(diff, dict) else 0,
                    "baseline_snapshot": bool(diff.get("baseline_snapshot", False)) if isinstance(diff, dict) else False,
                },
            }
        return {
            "schema_version": "geowatch-sanctions-summary-v1",
            "authorities": authorities,
            "ofac": {
                "status": "blocked_endpoint_validation",
                "detail": "OFAC parser/registry exist; automated refresh remains disabled until a current SLS export/API endpoint is validated.",
            },
            "legal_effect_requires_jurisdiction_specific_review": True,
        }

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/login":
            return self._send_json(405, {"error": "method not allowed"})
        login_key = self._login_key()
        if not login_allowed(login_key):
            return self._send_text(429, login_html(invalid=True), "text/html; charset=utf-8")
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length < 0 or length > 4096:
            record_login_failure(login_key)
            return self._send_json(413, {"error": "request too large"})
        body = self.rfile.read(length)
        if not verify_login_body(body, API_TOKEN):
            record_login_failure(login_key)
            return self._send_text(401, login_html(invalid=True), "text/html; charset=utf-8")
        clear_login_failures(login_key)
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

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .consumers import build_consumer_feed, consumer_profile_path, load_profile
from .dashboard import dashboard_html, map_points
from .episode_reports import build_episode_feed
from .geopolitics import GeopoliticalKnowledge
from .metrics import operational_snapshot, prometheus_text
from .reports import build_feed
from .review import build_review_queue
from .storage_factory import backend_name, open_store
from .validation import source_coverage_inventory

API_TOKEN = os.environ.get("GEOWATCH_API_TOKEN")


class Handler(BaseHTTPRequestHandler):
    server_version = "GeopoliticalWatch/0.8"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/health":
            return self._send_json(200, {"status": "ok", "service": "geopolitical-watch", "version": "0.8.0", "storage_backend": backend_name()})
        if path == "/dashboard":
            return self._send_text(200, dashboard_html(), "text/html; charset=utf-8")
        if API_TOKEN and self.headers.get("Authorization") != f"Bearer {API_TOKEN}":
            return self._send_json(401, {"error": "unauthorized"})

        store = open_store()
        try:
            if path == "/metrics":
                return self._send_text(200, prometheus_text(operational_snapshot(store)), "text/plain; version=0.0.4; charset=utf-8")
            if path == "/v2/operational":
                return self._send_json(200, operational_snapshot(store))
            if path == "/v2/coverage":
                return self._send_json(200, source_coverage_inventory(store, run_limit=_int(query, "limit", 5000) or 5000))
            if path == "/v2/review-queue":
                episodes = store.load_episodes(limit=_int(query, "episode_limit", 500) or 500)
                event_ids = sorted({event_id for episode in episodes for event_id in episode.event_ids})
                items = build_review_queue(
                    episodes,
                    claims=store.load_claims(),
                    events=store.load_events_by_ids(event_ids),
                    evidence=store.load_evidence(),
                    limit=_int(query, "limit", 200) or 200,
                )
                return self._send_json(200, {
                    "schema_version": "geowatch-review-queue-v1",
                    "items": [item.to_dict() for item in items],
                })
            if path == "/v2/map":
                return self._send_json(200, {"schema_version": "geowatch-map-v1", "points": map_points(store, limit=_int(query, "limit", 500) or 500)})
            if path == "/v2/alerts/pending":
                rows = store.pending_alerts(limit=_int(query, "limit", 100) or 100)
                return self._send_json(200, {"schema_version": "geowatch-alert-outbox-v1", "alerts": [row.get("payload") or row for row in rows]})
            if path.startswith("/v2/consumers/") and path.endswith("/feed"):
                parts = path.split("/")
                if len(parts) != 5:
                    return self._send_json(404, {"error": "not found"})
                name = parts[3]
                try:
                    profile_path = consumer_profile_path(name)
                except ValueError:
                    return self._send_json(400, {"error": "invalid consumer name"})
                if not profile_path.exists():
                    return self._send_json(404, {"error": "consumer profile not found"})
                return self._send_json(200, build_consumer_feed(store, load_profile(profile_path)))
            if path == "/v1/reports/latest":
                return self._report_or_404(store.latest_report("situational"))
            if path == "/v1/feed":
                report = store.latest_report("situational")
                return self._send_json(200, build_feed(report)) if report else self._send_json(404, {"error": "no report available"})
            if path == "/v2/reports/latest":
                return self._report_or_404(store.latest_report("episode_situational"))
            if path == "/v2/feed":
                report = store.latest_report("episode_situational")
                return self._send_json(200, build_episode_feed(report)) if report else self._send_json(404, {"error": "no episode report available"})
            if path == "/v2/episodes":
                return self._send_json(200, {
                    "schema_version": "geowatch-episodes-v2",
                    "episodes": store.list_episode_records(
                        country=_one(query, "country"), state=_one(query, "state"), since=_one(query, "since"),
                        min_strength=_int(query, "min_strength"), limit=_int(query, "limit", 100) or 100,
                    ),
                })
            if path.startswith("/v2/episodes/"):
                episode_id = path.split("/", 3)[3]
                return self._episode_detail(store, episode_id)
            if path == "/v2/events":
                return self._send_json(200, {"schema_version": "geowatch-events-v2", "events": store.list_events(since=_one(query, "since"), country=_one(query, "country"), limit=_int(query, "limit", 200) or 200)})
            if path == "/v2/changes":
                since = _one(query, "since") or "1970-01-01T00:00:00+00:00"
                return self._send_json(200, {"schema_version": "geowatch-changes-v1", "changes": store.changes_since(since, limit=_int(query, "limit", 500) or 500)})
            return self._send_json(404, {"error": "not found"})
        finally:
            store.close()

    def _episode_detail(self, store, episode_id: str) -> None:
        episode = store.get_episode(episode_id)
        if episode is None:
            return self._send_json(404, {"error": "episode not found", "episode_id": episode_id})
        event_rows = store.load_events_by_ids(episode.event_ids)
        claim_rows = store.load_claims(episode_id=episode_id)
        evidence_rows = store.load_evidence(episode_id=episode_id)
        entity_ids = set(episode.actor_entity_ids) | set(episode.infrastructure_entity_ids) | set(episode.other_entity_ids)
        entities = [row for row in store.load_entities() if row.entity_id in entity_ids]
        changes = [row for row in store.changes_since(episode.started_at, limit=5000) if row.get("episode_id") == episode_id]
        try:
            context = GeopoliticalKnowledge.from_files().context_for_episode(
                episode, claims=claim_rows, entities=entities, events=event_rows
            )
        except (FileNotFoundError, json.JSONDecodeError):
            context = {"context_not_evidence": True, "status": "knowledge_layer_unavailable"}
        return self._send_json(200, {
            "schema_version": "geowatch-episode-detail-v2", "episode": episode.to_dict(),
            "claims": [row.to_dict() for row in claim_rows], "evidence": [row.to_dict() for row in evidence_rows],
            "entities": [row.to_dict() for row in entities], "events": [row.to_dict() for row in event_rows],
            "changes": changes, "strategic_context": context,
        })

    def _report_or_404(self, report: dict | None) -> None:
        return self._send_json(200, report) if report is not None else self._send_json(404, {"error": "no report available"})

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, status: int, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _one(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    return values[0] if values and values[0] else None


def _int(query: dict[str, list[str]], key: str, default: int | None = None) -> int | None:
    value = _one(query, key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def main() -> int:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

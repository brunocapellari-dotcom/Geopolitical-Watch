from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import __version__
from .actor_profiles import ActorProfiles
from .backfill_planner import BackfillPlanner
from .consumers import build_consumer_feed, consumer_profile_path, load_profile
from .critical_infrastructure import CriticalInfrastructureGraph
from .dashboard import dashboard_html, map_points
from .episode_reports import build_episode_feed
from .event_graph import build_event_graph, related_event_ids
from .escalation import EscalationLibrary
from .forecasting import forecast_summary
from .geopolitics import GeopoliticalKnowledge
from .global_profiles import GlobalProfileRegistry
from .historical_corpus import HistoricalCorpus
from .live_aircraft import LiveAircraftError, aircraft_route, aircraft_snapshot
from .live_vessels import provider_status as vessel_provider_status, vessel_snapshot
from .metrics import operational_snapshot, prometheus_text
from .profile_enrichment import ProfileEnrichmentQueue
from .readiness import current_code_readiness_estimate
from .reports import build_feed
from .review import build_review_queue
from .security_systems import SecuritySystems
from .source_activation import SourceActivationRegistry
from .strategic_graph import StrategicGraph
from .strategic_state import list_forecasts, list_operations, list_review_decisions
from .storage_factory import backend_name, open_store
from .validation import source_coverage_inventory
from .v011_report import build_acceleration_report

API_TOKEN = os.environ.get("GEOWATCH_API_TOKEN")


def _reviewed_terms() -> set[str]:
    return {value.strip() for value in os.environ.get("GEOWATCH_REVIEWED_SOURCE_TERMS", "").split(",") if value.strip()}


class Handler(BaseHTTPRequestHandler):
    server_version = f"GeopoliticalWatch/{__version__}"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/health":
            return self._send_json(200, {"status": "ok", "service": "geopolitical-watch", "version": __version__, "storage_backend": backend_name()})
        if path == "/dashboard":
            return self._send_text(200, dashboard_html(), "text/html; charset=utf-8")
        if API_TOKEN and self.headers.get("Authorization") != f"Bearer {API_TOKEN}":
            return self._send_json(401, {"error": "unauthorized"})

        if path == "/v2/live/aircraft":
            try:
                payload = aircraft_snapshot(_one(query, "lat"), _one(query, "lon"), _one(query, "dist_nm") or 150)
                return self._send_json(200, payload)
            except ValueError as exc:
                return self._send_json(400, {"error": str(exc)})
            except LiveAircraftError as exc:
                return self._send_json(503, {"error": str(exc), "provider": "adsb.lol"})
        if path == "/v2/live/aircraft/route":
            try:
                payload = aircraft_route(_one(query, "callsign"), _one(query, "lat"), _one(query, "lon"))
                return self._send_json(200, payload)
            except ValueError as exc:
                return self._send_json(400, {"error": str(exc)})
            except LiveAircraftError as exc:
                return self._send_json(503, {"error": str(exc), "provider": "adsb.lol"})
        if path == "/v2/live/vessels":
            return self._send_json(200, vessel_snapshot())
        if path == "/v2/live/vessels/status":
            return self._send_json(200, vessel_provider_status())

        if path == "/v2/source-activation":
            return self._send_json(200, SourceActivationRegistry.from_json().evaluate(env=os.environ, reviewed_terms=_reviewed_terms()))
        if path == "/v2/backfill-plan":
            activation=SourceActivationRegistry.from_json().evaluate(env=os.environ, reviewed_terms=_reviewed_terms())
            limit=_int(query,"per_source_limit",2)
            return self._send_json(200,{"schema_version":"geowatch-backfill-queue-v1","windows":BackfillPlanner.from_json().queue(activation,per_source_limit=limit)})
        if path == "/v2/geopolitics/profile-progress":
            return self._send_json(200,ProfileEnrichmentQueue.from_files().progress())
        if path == "/v2/acceleration":
            return self._send_json(200,build_acceleration_report(env=dict(os.environ),reviewed_terms=_reviewed_terms()))

        store = open_store()
        try:
            if path == "/metrics":
                return self._send_text(200, prometheus_text(operational_snapshot(store)), "text/plain; version=0.0.4; charset=utf-8")
            if path == "/v2/operational":
                return self._send_json(200, operational_snapshot(store))
            if path == "/v2/readiness":
                return self._send_json(200, current_code_readiness_estimate())
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
                return self._send_json(200, {"schema_version": "geowatch-review-queue-v1", "items": [item.to_dict() for item in items]})
            if path == "/v2/review-decisions":
                return self._send_json(200, {"schema_version": "geowatch-review-decisions-v1", "decisions": list_review_decisions(store, episode_id=_one(query, "episode_id"), limit=_int(query, "limit", 200) or 200)})
            if path == "/v2/episode-operations":
                return self._send_json(200, {"schema_version": "geowatch-episode-operations-v1", "operations": list_operations(store, limit=_int(query, "limit", 200) or 200)})
            if path == "/v2/forecasts":
                rows = list_forecasts(store, status=_one(query, "status"), limit=_int(query, "limit", 1000) or 1000)
                return self._send_json(200, {"schema_version": "geowatch-forecasts-v1", "forecasts": rows})
            if path == "/v2/forecasts/summary":
                return self._send_json(200, {"schema_version": "geowatch-forecast-calibration-v1", **forecast_summary(list_forecasts(store))})
            if path == "/v2/geopolitics/countries":
                country = _one(query, "country")
                registry = GlobalProfileRegistry.from_files()
                if country:
                    profile = registry.profile(country)
                    return self._send_json(200, {"schema_version": "geowatch-country-profile-v1", "profile": profile}) if profile else self._send_json(404, {"error": "country profile not found"})
                return self._send_json(200, {"schema_version": "geowatch-country-profile-list-v1", "coverage": registry.coverage(), "profiles": registry.list_profiles(status=_one(query, "status"))})
            if path == "/v2/geopolitics/actors":
                actors = ActorProfiles.from_json()
                actor = _one(query, "actor_id")
                if actor:
                    profile = actors.profile(actor)
                    return self._send_json(200, {"schema_version": "geowatch-actor-profile-v1", "profile": profile}) if profile else self._send_json(404, {"error": "actor profile not found"})
                return self._send_json(200, {"schema_version": "geowatch-actor-profile-list-v1", "profiles": actors.list(_one(query, "actor_type"))})
            if path == "/v2/geopolitics/security-systems":
                systems = SecuritySystems.from_json(); country = _one(query, "country")
                return self._send_json(200, {"schema_version": systems.payload.get("schema_version"), "systems": systems.memberships(country) if country else list(systems.systems.values())})
            if path == "/v2/geopolitics/infrastructure":
                graph = CriticalInfrastructureGraph.from_json(); node_id = _one(query, "node_id"); country = _one(query, "country")
                if node_id:
                    node = graph.node(node_id); return self._send_json(200, {"schema_version": "geowatch-infrastructure-node-v1", "node": node}) if node else self._send_json(404, {"error": "infrastructure node not found"})
                return self._send_json(200, {"schema_version": "geowatch-critical-infrastructure-list-v1", "summary": graph.summary(), "nodes": graph.nodes_for_country(country) if country else [{**row, "context_not_evidence": True} for row in graph.nodes.values()]})
            if path == "/v2/geopolitics/history":
                corpus = HistoricalCorpus.from_json(); cutoff = _one(query, "as_of")
                return self._send_json(200, {"schema_version": "geowatch-historical-corpus-api-v1", "summary": corpus.summary(), "cases": corpus.as_of(cutoff) if cutoff else list(corpus.cases.values())})
            if path == "/v2/geopolitics/graph":
                return self._send_json(200, StrategicGraph.from_files().export_graph())
            if path == "/v2/history/snapshot":
                as_of = _one(query, "as_of")
                if not as_of:
                    return self._send_json(400, {"error": "as_of is required"})
                return self._send_json(200, {
                    "schema_version": "geowatch-point-in-time-snapshot-v1",
                    "as_of": as_of,
                    "objects": store.snapshot_as_of(
                        as_of,
                        object_type=_one(query, "object_type"),
                        limit=_int(query, "limit", 5000) or 5000,
                    ),
                })
            if path == "/v2/history/versions":
                object_type = _one(query, "object_type")
                object_id = _one(query, "object_id")
                if not object_type or not object_id:
                    return self._send_json(400, {"error": "object_type and object_id are required"})
                return self._send_json(200, {
                    "schema_version": "geowatch-object-version-history-v1",
                    "object_type": object_type,
                    "object_id": object_id,
                    "versions": store.list_versions(object_type, object_id),
                })
            if path == "/v2/event-graph":
                requested_episode = _one(query, "episode_id")
                if requested_episode:
                    episode = store.get_episode(requested_episode)
                    episodes = [episode] if episode is not None else []
                else:
                    episodes = store.load_episodes(limit=_int(query, "episode_limit", 500) or 500)
                event_ids = sorted({event_id for episode in episodes for event_id in episode.event_ids})
                events = store.load_events_by_ids(event_ids)
                return self._send_json(200, build_event_graph(episodes, events, episode_id=requested_episode))
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
                return self._send_json(200, {"schema_version": "geowatch-episodes-v2", "episodes": store.list_episode_records(
                    country=_one(query, "country"), state=_one(query, "state"), since=_one(query, "since"),
                    min_strength=_int(query, "min_strength"), limit=_int(query, "limit", 100) or 100,
                )})
            if path.startswith("/v2/episodes/"):
                return self._episode_detail(store, path.split("/", 3)[3])
            if path == "/v2/events":
                return self._send_json(200, {"schema_version": "geowatch-events-v2", "events": store.list_events(since=_one(query, "since"), country=_one(query, "country"), limit=_int(query, "limit", 200) or 200)})
            if path.startswith("/v2/events/"):
                return self._event_detail(store, path.split("/", 3)[3])
            if path == "/v2/relationships":
                rows = store.load_relationships(
                    entity_id=_one(query, "entity_id"),
                    relationship_type=_one(query, "relationship_type"),
                )
                limit = _int(query, "limit", 500) or 500
                return self._send_json(200, {
                    "schema_version": "geowatch-relationships-v1",
                    "relationships": [row.to_dict() for row in rows[:max(1, min(limit, 5000))]],
                })
            if path == "/v2/changes":
                since = _one(query, "since") or "1970-01-01T00:00:00+00:00"
                return self._send_json(200, {"schema_version": "geowatch-changes-v1", "changes": store.changes_since(since, limit=_int(query, "limit", 500) or 500)})
            return self._send_json(404, {"error": "not found"})
        finally:
            store.close()

    def _event_detail(self, store, event_id: str) -> None:
        events = store.load_events_by_ids([event_id])
        if not events:
            return self._send_json(404, {"error": "event not found", "event_id": event_id})
        event = events[0]
        episodes = [
            episode for episode in store.load_episodes(limit=5000)
            if event_id in episode.event_ids
        ]
        graph_event_ids = sorted({eid for episode in episodes for eid in episode.event_ids})
        graph_events = store.load_events_by_ids(graph_event_ids)
        graph = build_event_graph(episodes, graph_events)
        event_links = [
            link for link in graph["links"]
            if link.get("source_event_id") == event_id or link.get("target_event_id") == event_id
        ]
        return self._send_json(200, {
            "schema_version": "geowatch-event-detail-v1",
            "event": event.to_dict(),
            "episode_ids": [episode.episode_id for episode in episodes],
            "related_event_ids": related_event_ids(graph, event_id),
            "relationships": event_links,
            "causality_not_automatically_inferred": True,
        })

    def _episode_detail(self, store, episode_id: str) -> None:
        episode = store.get_episode(episode_id)
        if episode is None:
            return self._send_json(404, {"error": "episode not found", "episode_id": episode_id})
        event_rows = store.load_events_by_ids(episode.event_ids)
        claim_rows = store.load_claims(episode_id=episode_id)
        evidence_rows = store.load_evidence(episode_id=episode_id)
        entity_ids = set(episode.actor_entity_ids) | set(episode.infrastructure_entity_ids) | set(episode.other_entity_ids)
        entities = [row for row in store.load_entities() if row.entity_id in entity_ids]
        relationship_by_id = {}
        for entity_id in sorted(entity_ids):
            for relationship in store.load_relationships(entity_id=entity_id):
                relationship_by_id[relationship.relationship_id] = relationship
        relationships = list(relationship_by_id.values())
        changes = [row for row in store.changes_since(episode.started_at, limit=5000) if row.get("episode_id") == episode_id]
        try:
            context = GeopoliticalKnowledge.from_files().context_for_episode(episode, claims=claim_rows, entities=entities, events=event_rows)
        except (FileNotFoundError, json.JSONDecodeError):
            context = {"context_not_evidence": True, "status": "knowledge_layer_unavailable"}
        try:
            graph_context = StrategicGraph.from_files().context_for_episode(episode, entities=entities)
        except (FileNotFoundError, json.JSONDecodeError):
            graph_context = {"context_not_evidence": True, "status": "strategic_graph_unavailable"}
        try:
            escalation = EscalationLibrary.from_json().detect(events=event_rows, claims=claim_rows)
        except (FileNotFoundError, json.JSONDecodeError):
            escalation = {"indicator_score_not_probability": True, "status": "indicator_library_unavailable"}
        return self._send_json(200, {
            "schema_version": "geowatch-episode-detail-v2", "episode": episode.to_dict(),
            "claims": [row.to_dict() for row in claim_rows], "evidence": [row.to_dict() for row in evidence_rows],
            "entities": [row.to_dict() for row in entities], "events": [row.to_dict() for row in event_rows],
            "relationships": [row.to_dict() for row in relationships],
            "changes": changes, "strategic_context": context, "strategic_graph_context": graph_context,
            "escalation_readout": escalation, "review_decisions": list_review_decisions(store, episode_id=episode_id, limit=200),
            "forecasts": [row for row in list_forecasts(store, limit=5000) if row.get("subject_type") == "episode" and row.get("subject_id") == episode_id],
        })

    def _report_or_404(self, store_report: dict | None) -> None:
        return self._send_json(200, store_report) if store_report is not None else self._send_json(404, {"error": "no report available"})

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def _send_text(self, status: int, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


def _one(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key); return values[0] if values and values[0] else None


def _int(query: dict[str, list[str]], key: str, default: int | None = None) -> int | None:
    value = _one(query, key)
    if value is None: return default
    try: return int(value)
    except ValueError: return default


def main() -> int:
    host = os.environ.get("HOST", "0.0.0.0"); port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), Handler); server.serve_forever(); return 0


if __name__ == "__main__":
    raise SystemExit(main())

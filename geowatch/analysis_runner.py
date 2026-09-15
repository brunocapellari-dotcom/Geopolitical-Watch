from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .alerts import enqueue_alerts, evaluate_alerts, load_policies
from .claim_verification import verify_claims
from .convergence import converge_events
from .core import cluster_events
from .entities import EntityResolver
from .episode_reports import build_episode_report, render_episode_markdown
from .quality import load_profiles
from .reports import build_report, render_markdown
from .storage_factory import open_store


def run_analysis(
    *,
    config_path: str | Path = "config/sources.production.json",
    db_path: str | Path | None = None,
) -> dict[str, object]:
    """Run deterministic analysis over already-collected events.

    Collection cadence is deliberately independent from this function. This keeps
    fast physical/network feeds from forcing expensive convergence on every poll.
    """
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    generated_at = now.isoformat()
    store = open_store(db_path)
    try:
        profiles = load_profiles(config.get("source_quality_profiles", "config/source_quality.json"))
        report_cfg = config.get("report", {})
        analysis_since = (now - timedelta(hours=max(1, int(report_cfg.get("lookback_hours", 72))))).isoformat()
        analysis_events = store.load_events_since(analysis_since)
        clusters = cluster_events(
            analysis_events,
            threshold=float(report_cfg.get("title_similarity_threshold", 0.78)),
            max_time_delta_hours=float(report_cfg.get("cluster_time_hours", 36)),
            max_distance_km=float(report_cfg.get("cluster_distance_km", 250)),
        )
        report = build_report(
            clusters,
            generated_at=generated_at,
            min_priority=int(report_cfg.get("min_priority", 0)),
            max_events=int(report_cfg.get("max_events", 20)),
            max_news_per_event=int(report_cfg.get("max_news_per_event", 5)),
            source_profiles=profiles,
        )
        store.upsert_clusters(clusters, generated_at)
        store.upsert_report(report, render_markdown(report))

        convergence_cfg = config.get("convergence", {})
        episode_days = max(30, int(convergence_cfg.get("episode_lookback_days", 30)))
        episode_since = (now - timedelta(days=episode_days)).isoformat()
        episode_events = store.load_events_since(episode_since)
        seed_resolver = EntityResolver.from_json(convergence_cfg.get("entity_catalog", "config/entities.json"))
        resolver = EntityResolver([*seed_resolver.entities.values(), *store.load_entities()])
        episodes, claims, evidence, entities, changes = converge_events(
            episode_events,
            existing_episodes=store.load_episodes(since=episode_since),
            existing_claims=store.load_claims(),
            existing_evidence=store.load_evidence(),
            resolver=resolver,
            attach_threshold=float(convergence_cfg.get("attach_threshold", 0.43)),
            now=now,
        )
        store.upsert_entities(entities)
        store.upsert_evidence(evidence)
        store.upsert_episodes(episodes)
        store.upsert_claims(claims)
        store.record_changes(changes)

        verdicts = verify_claims(claims, evidence=evidence, events=episode_events, source_profiles=profiles)
        alert_cfg = config.get("alerts", {})
        alerts = evaluate_alerts(
            episodes,
            changes,
            load_policies(alert_cfg.get("policy_file", "config/alerts.json")),
            created_at=generated_at,
            claim_verdicts=verdicts,
        )
        alerts_enqueued = enqueue_alerts(store, alerts)

        episode_report = build_episode_report(
            episodes,
            claims=claims,
            evidence=evidence,
            entities=entities,
            events=episode_events,
            generated_at=generated_at,
            max_episodes=int(convergence_cfg.get("max_report_episodes", 50)),
        )
        store.upsert_report(episode_report, render_episode_markdown(episode_report))
        return {
            "generated_at": generated_at,
            "analysis_events": len(analysis_events),
            "clusters": len(clusters),
            "report_id": report["report_id"],
            "episodes": len(episodes),
            "claims": len(claims),
            "verdicts": len(verdicts),
            "episode_report_id": episode_report["report_id"],
            "episode_changes": len(changes),
            "alerts_generated": len(alerts),
            "alerts_enqueued": alerts_enqueued,
        }
    finally:
        store.close()

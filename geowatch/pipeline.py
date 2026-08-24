from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from .alerts import enqueue_alerts, evaluate_alerts, load_policies
from .core import cluster_events
from .convergence import converge_events
from .entities import EntityResolver
from .episode_reports import build_episode_report, render_episode_markdown
from .geo import canonicalize_event
from .history import TimeWindow, iter_windows, overlap_start, parse_utc
from .quality import load_profiles
from .raw_store import open_raw_store
from .reports import build_report, render_markdown
from .sources import acled, firms, gdacs, gdelt, reliefweb, ucdp
from .storage_factory import open_store


def run(config_path: str | Path = "config/sources.json", db_path: str | Path | None = None, raw_root: str | Path = "data/raw", reports_root: str | Path = "reports") -> dict:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    collected_at = now.isoformat()
    raw_store = open_raw_store(raw_root)
    store = open_store(db_path)
    profiles = load_profiles(config.get("source_quality_profiles", "config/source_quality.json"))
    source_results: list[dict[str, object]] = []
    history_cfg = config.get("history", {})
    default_lookback_hours = int(history_cfg.get("default_lookback_hours", 24))
    overlap_minutes = int(history_cfg.get("checkpoint_overlap_minutes", 30))

    for spec in config.get("sources", []):
        if not spec.get("enabled", False):
            continue
        source_id = str(spec["source_id"])
        started_at = datetime.now(timezone.utc).isoformat()
        run_id = uuid4().hex
        request_meta: dict[str, object] = {"kind": spec.get("kind")}
        try:
            checkpoint = store.get_checkpoint(source_id)
            payloads, urls, parser = _collect_incremental(spec, checkpoint=checkpoint, now=now, default_lookback_hours=default_lookback_hours, overlap_minutes=overlap_minutes, request_meta=request_meta)
            source_events = []
            for index, payload in enumerate(payloads):
                url = urls[index] if index < len(urls) else None
                raw_ref, digest = raw_store.put(source_id, collected_at, payload, str(spec.get("extension", "json")))
                store.add_artifact(artifact_id=f"{source_id}:{digest}", source_id=source_id, sha256=digest, collected_at=collected_at, observed_url=url, path=raw_ref, bytes_count=len(payload))
                parsed = parser(payload, source_id=source_id, collected_at=collected_at, raw_ref=raw_ref)
                source_events.extend(canonicalize_event(event) for event in parsed)
            store.upsert_events(source_events)
            last_reference = max((event.reference_at for event in source_events), default=None)
            store.update_checkpoint(source_id, last_success_at=collected_at, last_reference_at=last_reference, cursor={"observed_urls": urls[-3:]})
            finished_at = datetime.now(timezone.utc).isoformat()
            store.record_run(run_id=run_id, source_id=source_id, started_at=started_at, finished_at=finished_at, status="ok", records=len(source_events), request=request_meta)
            source_results.append({"source_id": source_id, "status": "ok", "records": len(source_events), "requests": len(payloads)})
        except Exception as exc:
            finished_at = datetime.now(timezone.utc).isoformat()
            error = f"{type(exc).__name__}: {exc}"
            store.record_run(run_id=run_id, source_id=source_id, started_at=started_at, finished_at=finished_at, status="error", records=0, request=request_meta, error=error)
            source_results.append({"source_id": source_id, "status": "error", "error": error})

    report_cfg = config.get("report", {})
    analysis_since = (now - timedelta(hours=max(1, int(report_cfg.get("lookback_hours", 72))))).isoformat()
    analysis_events = store.load_events_since(analysis_since)
    clusters = cluster_events(analysis_events, threshold=float(report_cfg.get("title_similarity_threshold", 0.78)), max_time_delta_hours=float(report_cfg.get("cluster_time_hours", 36)), max_distance_km=float(report_cfg.get("cluster_distance_km", 250)))
    report = build_report(clusters, generated_at=collected_at, min_priority=int(report_cfg.get("min_priority", 0)), max_events=int(report_cfg.get("max_events", 20)), max_news_per_event=int(report_cfg.get("max_news_per_event", 5)), source_profiles=profiles)
    markdown = render_markdown(report)
    store.upsert_clusters(clusters, collected_at)
    store.upsert_report(report, markdown)

    convergence_cfg = config.get("convergence", {})
    episode_since = (now - timedelta(days=max(30, int(convergence_cfg.get("episode_lookback_days", 180))))).isoformat()
    episode_events = store.load_events_since(episode_since)
    seed_resolver = EntityResolver.from_json(convergence_cfg.get("entity_catalog", "config/entities.json"))
    resolver = EntityResolver([*seed_resolver.entities.values(), *store.load_entities()])
    episodes, claims, evidence, entities, changes = converge_events(
        episode_events, existing_episodes=store.load_episodes(since=episode_since), existing_claims=store.load_claims(),
        existing_evidence=store.load_evidence(), resolver=resolver, attach_threshold=float(convergence_cfg.get("attach_threshold", 0.43)), now=now,
    )
    store.upsert_entities(entities)
    store.upsert_evidence(evidence)
    store.upsert_episodes(episodes)
    store.upsert_claims(claims)
    store.record_changes(changes)

    alert_cfg = config.get("alerts", {})
    alerts = evaluate_alerts(episodes, changes, load_policies(alert_cfg.get("policy_file", "config/alerts.json")), created_at=collected_at)
    alerts_enqueued = enqueue_alerts(store, alerts)

    episode_report = build_episode_report(episodes, claims=claims, evidence=evidence, entities=entities, events=episode_events, generated_at=collected_at, max_episodes=int(convergence_cfg.get("max_report_episodes", 50)))
    episode_markdown = render_episode_markdown(episode_report)
    store.upsert_report(episode_report, episode_markdown)
    store.close()
    _write_reports(reports_root, collected_at, report, markdown)
    _write_episode_reports(reports_root, collected_at, episode_report, episode_markdown)

    return {"generated_at": collected_at, "source_results": source_results, "analysis_events": len(analysis_events), "clusters": len(clusters), "report_id": report["report_id"], "episodes": len(episodes), "episode_report_id": episode_report["report_id"], "episode_changes": len(changes), "alerts_generated": len(alerts), "alerts_enqueued": alerts_enqueued}


def backfill(source_id: str, start: str, end: str, *, config_path: str | Path = "config/sources.json", db_path: str | Path | None = None, raw_root: str | Path = "data/raw", chunk_hours: int = 6) -> dict:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    spec = next((row for row in config.get("sources", []) if row.get("source_id") == source_id), None)
    if spec is None:
        raise ValueError(f"Unknown source_id: {source_id}")
    kind = spec.get("kind")
    store = open_store(db_path)
    raw_store = open_raw_store(raw_root)
    collected_at = datetime.now(timezone.utc).isoformat()
    total_records = 0
    requests = 0
    if kind == "gdelt":
        for window in iter_windows(start, end, hours=max(1, chunk_hours)):
            params = window.gdelt_params()
            payload, url = gdelt.collect(query=spec.get("query", gdelt.DEFAULT_QUERY), maxrecords=int(spec.get("maxrecords", 250)), start_datetime=params["startdatetime"], end_datetime=params["enddatetime"])
            total_records += _persist_backfill_payload(store, raw_store, spec, payload, url, collected_at, gdelt.parse); requests += 1
    elif kind == "ucdp":
        payloads, urls = ucdp.collect_all(version=spec.get("version", ucdp.DEFAULT_VERSION), pagesize=int(spec.get("pagesize", 1000)), start_date=parse_utc(start).date().isoformat(), end_date=parse_utc(end).date().isoformat())
        for payload, url in zip(payloads, urls):
            total_records += _persist_backfill_payload(store, raw_store, spec, payload, url, collected_at, ucdp.parse)
        requests += len(payloads)
    elif kind == "firms":
        current = parse_utc(start).date(); finish = parse_utc(end).date()
        while current <= finish:
            day_range = min(5, (finish - current).days + 1)
            payload, url = firms.collect(sensor=spec.get("sensor", "VIIRS_SNPP_NRT"), area=spec.get("area", "world"), day_range=day_range, date=current.isoformat())
            total_records += _persist_backfill_payload(store, raw_store, spec, payload, url, collected_at, firms.parse); current += timedelta(days=day_range); requests += 1
    elif kind == "acled":
        query = {"event_date": f"{parse_utc(start).date().isoformat()}|{parse_utc(end).date().isoformat()}", "event_date_where": "BETWEEN"}
        payloads, urls = acled.collect_all(query=query, limit=int(spec.get("limit", 5000)))
        for payload, url in zip(payloads, urls):
            total_records += _persist_backfill_payload(store, raw_store, spec, payload, url, collected_at, acled.parse)
        requests += len(payloads)
    else:
        store.close(); raise NotImplementedError(f"Backfill not implemented for source kind: {kind}")
    store.update_checkpoint(source_id, last_success_at=collected_at, last_reference_at=end); store.close()
    return {"source_id": source_id, "start": start, "end": end, "requests": requests, "records": total_records}


def _collect_incremental(spec: dict, *, checkpoint: dict | None, now: datetime, default_lookback_hours: int, overlap_minutes: int, request_meta: dict[str, object]):
    kind = spec["kind"]
    if kind == "gdelt":
        start = overlap_start(checkpoint.get("last_success_at") if checkpoint else None, default_lookback_hours=int(spec.get("lookback_hours", default_lookback_hours)), overlap_minutes=overlap_minutes, now=now)
        params = TimeWindow(start, now).gdelt_params(); request_meta.update(params)
        payload, url = gdelt.collect(query=spec.get("query", gdelt.DEFAULT_QUERY), maxrecords=int(spec.get("maxrecords", 250)), start_datetime=params["startdatetime"], end_datetime=params["enddatetime"])
        return [payload], [url], gdelt.parse
    if kind == "reliefweb":
        payload, url = reliefweb.collect(query=spec.get("query", "conflict war hostilities displacement"), limit=int(spec.get("limit", 100))); return [payload], [url], reliefweb.parse
    if kind == "ucdp":
        start_date = None
        if checkpoint and checkpoint.get("last_reference_at"):
            start_date = (parse_utc(checkpoint["last_reference_at"]) - timedelta(days=1)).date().isoformat(); request_meta["StartDate"] = start_date
        payloads, urls = ucdp.collect_all(version=spec.get("version", ucdp.DEFAULT_VERSION), pagesize=int(spec.get("pagesize", 1000)), start_date=start_date); return payloads, urls, ucdp.parse
    if kind == "firms":
        payload, url = firms.collect(sensor=spec.get("sensor", "VIIRS_SNPP_NRT"), area=spec.get("area", "world"), day_range=int(spec.get("day_range", 1))); return [payload], [url], firms.parse
    if kind == "gdacs":
        payload, url = gdacs.collect(query=spec.get("query")); return [payload], [url], gdacs.parse
    if kind == "acled":
        lookback_days = int(spec.get("lookback_days", 7))
        start = parse_utc(checkpoint["last_reference_at"]) - timedelta(days=1) if checkpoint and checkpoint.get("last_reference_at") else now - timedelta(days=max(1, lookback_days))
        query = {"event_date": f"{start.date().isoformat()}|{now.date().isoformat()}", "event_date_where": "BETWEEN"}; request_meta.update(query)
        payloads, urls = acled.collect_all(query=query, limit=int(spec.get("limit", 5000))); return payloads, urls, acled.parse
    raise ValueError(f"Unknown source kind: {kind}")


def _persist_backfill_payload(store, raw_store, spec: dict, payload: bytes, url: str, collected_at: str, parser) -> int:
    source_id = str(spec["source_id"])
    raw_ref, digest = raw_store.put(source_id, collected_at, payload, str(spec.get("extension", "json")))
    store.add_artifact(artifact_id=f"{source_id}:{digest}", source_id=source_id, sha256=digest, collected_at=collected_at, observed_url=url, path=raw_ref, bytes_count=len(payload))
    events = [canonicalize_event(event) for event in parser(payload, source_id=source_id, collected_at=collected_at, raw_ref=raw_ref)]
    store.upsert_events(events); return len(events)


def _write_reports(reports_root: str | Path, collected_at: str, report: dict, markdown: str) -> None:
    root = Path(reports_root); day_dir = root / collected_at[:10]; day_dir.mkdir(parents=True, exist_ok=True); stamp = collected_at.replace(":", "-").replace("+", "_")
    (day_dir / f"{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"); (day_dir / f"{stamp}.md").write_text(markdown, encoding="utf-8"); (root / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"); (root / "latest.md").write_text(markdown, encoding="utf-8")


def _write_episode_reports(reports_root: str | Path, collected_at: str, report: dict, markdown: str) -> None:
    root = Path(reports_root) / "episodes"; day_dir = root / collected_at[:10]; day_dir.mkdir(parents=True, exist_ok=True); stamp = collected_at.replace(":", "-").replace("+", "_")
    (day_dir / f"{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"); (day_dir / f"{stamp}.md").write_text(markdown, encoding="utf-8"); (root / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"); (root / "latest.md").write_text(markdown, encoding="utf-8")

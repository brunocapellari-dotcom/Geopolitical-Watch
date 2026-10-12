from __future__ import annotations

import argparse
import json

from .collector_scheduler import run_tick as scheduler_tick
from .consumers import build_consumer_feed, load_profile
from .delivery import dispatch_pending
from .episode_workflow import apply_merge, apply_split, revert_operation
from .evaluation import replay_episode_fixture, replay_fixture
from .forecasting import forecast_summary
from .metrics import operational_snapshot
from .pipeline import backfill, run
from .private_api_final import main as api_main
from .strategic_graph import StrategicGraph
from .strategic_state import (
    list_forecasts,
    record_forecast,
    record_review_decision,
    resolve_forecast,
)
from .storage_factory import open_store


def main() -> int:
    parser = argparse.ArgumentParser(prog="geowatch")
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect")
    collect.add_argument("--config", default="config/sources.json")
    collect.add_argument("--db", default=None, help="SQLite path or PostgreSQL DSN; env GEOWATCH_DB_URL is used when omitted")
    collect.add_argument("--raw", default="data/raw")
    collect.add_argument("--reports", default="reports")

    history = sub.add_parser("backfill")
    history.add_argument("--source", required=True)
    history.add_argument("--start", required=True, help="ISO date/datetime")
    history.add_argument("--end", required=True, help="ISO date/datetime")
    history.add_argument("--chunk-hours", type=int, default=6)
    history.add_argument("--config", default="config/sources.json")
    history.add_argument("--db", default=None)
    history.add_argument("--raw", default="data/raw")

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--fixture", default="tests/fixtures/clustering_eval.json")
    evaluate_episodes = sub.add_parser("evaluate-episodes")
    evaluate_episodes.add_argument("--fixture", default="tests/fixtures/episode_eval.json")
    evaluate_episodes.add_argument("--entities", default="config/entities.json")

    metrics = sub.add_parser("metrics")
    metrics.add_argument("--db", default=None)
    dispatch = sub.add_parser("dispatch-alerts")
    dispatch.add_argument("--db", default=None)
    dispatch.add_argument("--webhook", default=None)
    dispatch.add_argument("--limit", type=int, default=100)
    consumer = sub.add_parser("consumer-feed")
    consumer.add_argument("--db", default=None)
    consumer.add_argument("--profile", required=True)

    review = sub.add_parser("record-review")
    review.add_argument("--db", default=None)
    review.add_argument("--review-id", required=True)
    review.add_argument("--episode-id", required=True)
    review.add_argument("--decision", required=True)
    review.add_argument("--rationale", required=True)
    review.add_argument("--reviewer", default=None)

    forecast = sub.add_parser("forecast")
    forecast.add_argument("--db", default=None)
    forecast.add_argument("--subject-type", required=True)
    forecast.add_argument("--subject-id", required=True)
    forecast.add_argument("--question", required=True)
    forecast.add_argument("--probability", type=float, required=True)
    forecast.add_argument("--horizon", required=True)
    forecast.add_argument("--rationale", default="")
    resolve = sub.add_parser("resolve-forecast")
    resolve.add_argument("--db", default=None)
    resolve.add_argument("--forecast-id", required=True)
    resolve.add_argument("--outcome", choices=["yes", "no"], required=True)
    resolve.add_argument("--rationale", default="")
    forecast_metrics = sub.add_parser("forecast-summary")
    forecast_metrics.add_argument("--db", default=None)

    merge = sub.add_parser("merge-episodes")
    merge.add_argument("--db", default=None)
    merge.add_argument("--episode-id", action="append", required=True)
    merge.add_argument("--survivor", default=None)
    merge.add_argument("--reason", required=True)
    split = sub.add_parser("split-episode")
    split.add_argument("--db", default=None)
    split.add_argument("--episode-id", required=True)
    split.add_argument("--event-groups-json", required=True)
    split.add_argument("--reason", required=True)
    revert = sub.add_parser("revert-operation")
    revert.add_argument("--db", default=None)
    revert.add_argument("--operation-id", required=True)
    revert.add_argument("--reason", required=True)

    profile = sub.add_parser("country-profile")
    profile.add_argument("--country", required=True)
    sub.add_parser("scheduler-tick", help="Run one registry-scheduler collection/analysis tick and exit")
    single = sub.add_parser("source-once", help="Run one source in an isolated process and exit")
    single.add_argument("--source", required=True)
    analysis_once = sub.add_parser("analysis-once", help="Run deterministic analysis once and exit")
    analysis_once.add_argument("--config", default="config/sources.production.json")
    sub.add_parser("sanctions-once", help="Refresh official sanctions in an isolated process and exit")
    sub.add_parser("serve")
    args = parser.parse_args()

    if args.command == "serve":
        return api_main()
    if args.command == "scheduler-tick":
        print(json.dumps(scheduler_tick(), ensure_ascii=False))
        return 0
    if args.command == "source-once":
        from .source_collection import collect_source_once
        from .satellite_runtime import refresh_celestrak
        if args.source == "celestrak":
            result = refresh_celestrak(group="military")
        else:
            result = collect_source_once(args.source)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.command == "analysis-once":
        from .analysis_runner import run_analysis
        print(json.dumps(run_analysis(config_path=args.config), ensure_ascii=False))
        return 0
    if args.command == "sanctions-once":
        from .sanctions_runtime import refresh_official_sanctions
        print(json.dumps(refresh_official_sanctions(), ensure_ascii=False))
        return 0
    if args.command == "evaluate":
        print(json.dumps(replay_fixture(args.fixture), ensure_ascii=False, indent=2))
        return 0
    if args.command == "evaluate-episodes":
        print(json.dumps(replay_episode_fixture(args.fixture, entity_catalog=args.entities), ensure_ascii=False, indent=2))
        return 0
    if args.command == "country-profile":
        print(json.dumps(StrategicGraph.from_files().country_profile(args.country), ensure_ascii=False, indent=2))
        return 0

    if args.command in {
        "metrics",
        "dispatch-alerts",
        "consumer-feed",
        "record-review",
        "forecast",
        "resolve-forecast",
        "forecast-summary",
        "merge-episodes",
        "split-episode",
        "revert-operation",
    }:
        store = open_store(args.db)
        try:
            if args.command == "metrics":
                result = operational_snapshot(store)
            elif args.command == "dispatch-alerts":
                result = dispatch_pending(store, webhook_url=args.webhook, limit=args.limit)
            elif args.command == "consumer-feed":
                result = build_consumer_feed(store, load_profile(args.profile))
            elif args.command == "record-review":
                result = record_review_decision(store, review_id=args.review_id, episode_id=args.episode_id, decision=args.decision, rationale=args.rationale, reviewer=args.reviewer)
            elif args.command == "forecast":
                result = record_forecast(store, subject_type=args.subject_type, subject_id=args.subject_id, question=args.question, probability=args.probability, horizon_at=args.horizon, rationale=args.rationale)
            elif args.command == "resolve-forecast":
                result = resolve_forecast(store, args.forecast_id, outcome=args.outcome == "yes", rationale=args.rationale)
            elif args.command == "forecast-summary":
                result = forecast_summary(list_forecasts(store))
            elif args.command == "merge-episodes":
                result = apply_merge(store, args.episode_id, survivor_id=args.survivor, reason=args.reason)
            elif args.command == "split-episode":
                result = apply_split(store, args.episode_id, event_groups=json.loads(args.event_groups_json), reason=args.reason)
            else:
                result = revert_operation(store, args.operation_id, reason=args.reason)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        finally:
            store.close()

    if args.command == "backfill":
        result = backfill(args.source, args.start, args.end, config_path=args.config, db_path=args.db, raw_root=args.raw, chunk_hours=args.chunk_hours)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    result = run(args.config, args.db, args.raw, args.reports)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

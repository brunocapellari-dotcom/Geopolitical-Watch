from __future__ import annotations

import argparse
import json

from .api import main as api_main
from .consumers import build_consumer_feed, load_profile
from .delivery import dispatch_pending
from .evaluation import replay_episode_fixture, replay_fixture
from .metrics import operational_snapshot
from .pipeline import backfill, run
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
    sub.add_parser("serve")
    args = parser.parse_args()

    if args.command == "serve":
        return api_main()
    if args.command == "evaluate":
        print(json.dumps(replay_fixture(args.fixture), ensure_ascii=False, indent=2)); return 0
    if args.command == "evaluate-episodes":
        print(json.dumps(replay_episode_fixture(args.fixture, entity_catalog=args.entities), ensure_ascii=False, indent=2)); return 0
    if args.command == "metrics":
        store = open_store(args.db)
        try: print(json.dumps(operational_snapshot(store), ensure_ascii=False, indent=2))
        finally: store.close()
        return 0
    if args.command == "dispatch-alerts":
        store = open_store(args.db)
        try: print(json.dumps(dispatch_pending(store, webhook_url=args.webhook, limit=args.limit), ensure_ascii=False, indent=2))
        finally: store.close()
        return 0
    if args.command == "consumer-feed":
        store = open_store(args.db)
        try: print(json.dumps(build_consumer_feed(store, load_profile(args.profile)), ensure_ascii=False, indent=2))
        finally: store.close()
        return 0
    if args.command == "backfill":
        result = backfill(args.source, args.start, args.end, config_path=args.config, db_path=args.db, raw_root=args.raw, chunk_hours=args.chunk_hours)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0

    result = run(args.config, args.db, args.raw, args.reports)
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json

from .api import main as api_main
from .pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(prog="geowatch")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--config", default="config/sources.json")
    collect.add_argument("--db", default="data/geowatch.db")
    collect.add_argument("--raw", default="data/raw")
    collect.add_argument("--reports", default="reports")
    sub.add_parser("serve")
    args = parser.parse_args()
    if args.command == "serve":
        return api_main()
    result = run(args.config, args.db, args.raw, args.reports)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

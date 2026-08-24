from __future__ import annotations

import argparse
import json
from pathlib import Path

from geowatch.coverage_dashboard import build_source_coverage_dashboard
from geowatch.storage_factory import open_store


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/beta.db")
    parser.add_argument("--out", default="reports/beta_coverage.json")
    args = parser.parse_args()
    store = open_store(args.db)
    try:
        payload = build_source_coverage_dashboard(store)
    finally:
        store.close()
    path = Path(args.out); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

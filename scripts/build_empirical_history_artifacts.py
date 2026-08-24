from __future__ import annotations

import json
from pathlib import Path

from _repo_path import ensure_repo_path

ensure_repo_path()

from geowatch.empirical_history import EmpiricalHistory


def main() -> int:
    history = EmpiricalHistory.from_files()
    out = Path("generated/empirical")
    out.mkdir(parents=True, exist_ok=True)

    catalog = {
        "schema_version": "geowatch-empirical-history-catalog-v1",
        "cases": history.layered_cases(),
        "governance": {
            "layers_remain_distinct": True,
            "research_coded_history_is_not_live_event_evidence": True,
            "human_gold_requires_explicit_review": True,
        },
    }
    windows = {
        "schema_version": "geowatch-empirical-history-windows-v1",
        "windows": history.evaluation_windows(),
        "no_lookahead_required": True,
    }
    summary = history.summary()

    (out / "history_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "evaluation_windows.json").write_text(json.dumps(windows, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

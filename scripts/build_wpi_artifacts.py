from __future__ import annotations

import json
from pathlib import Path

from _repo_path import ensure_repo_path

ensure_repo_path()

from geowatch.wpi import download, select_candidates


def main() -> int:
    rows, url = download()
    candidates = select_candidates(rows, limit=300, min_per_water_body=3)
    out = Path("generated/wpi")
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "geowatch-wpi-candidates-v1",
        "source_url": url,
        "source_row_count": len(rows),
        "candidate_count": len(candidates),
        "nodes": candidates,
        "governance": {
            "structural_context_not_live_status": True,
            "candidate_score_not_criticality_probability": True,
            "current_conditions_require_current_port_authority_or_notice": True
        }
    }
    (out / "critical_port_candidates.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "schema_version": "geowatch-wpi-build-summary-v1",
        "source_row_count": len(rows),
        "candidate_count": len(candidates),
        "large_harbor_candidates": sum(1 for node in candidates if str(node.get("harbor_size") or "").casefold() == "large"),
        "with_container_facility": sum(1 for node in candidates if "Container" in node.get("facilities", [])),
        "with_oil_terminal": sum(1 for node in candidates if "Oil Terminal" in node.get("facilities", [])),
        "with_lng_terminal": sum(1 for node in candidates if "LNG Terminal" in node.get("facilities", [])),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

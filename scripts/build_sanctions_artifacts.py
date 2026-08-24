from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from geowatch.http import get
from geowatch.sanctions_feed import diff_designations, parse_uk_csv, parse_un_consolidated_xml, SanctionsDesignation


def _as_obj(row: dict) -> SanctionsDesignation:
    return SanctionsDesignation(
        designation_id=row["designation_id"],
        authority=row["authority"],
        list_name=row["list_name"],
        external_reference=row.get("external_reference"),
        name=row["name"],
        entity_type=row.get("entity_type") or "unknown",
        programs=tuple(row.get("programs") or ()),
        effective_date=row.get("effective_date"),
        source_url=row.get("source_url"),
        collected_at=row.get("collected_at") or "",
        evidence_class=row.get("evidence_class") or "observed",
    )


def _snapshot(path: Path, rows: list[SanctionsDesignation], *, source_url: str) -> dict:
    return {
        "schema_version":"geowatch-sanctions-snapshot-v1",
        "source_url":source_url,
        "designation_count":len(rows),
        "designations":[row.to_dict() for row in rows],
    }


def _load_previous(path: Path) -> list[SanctionsDesignation]:
    if not path.exists():
        return []
    payload=json.loads(path.read_text(encoding="utf-8"))
    return [_as_obj(row) for row in payload.get("designations",[])]


def main() -> int:
    collected_at=datetime.now(timezone.utc).isoformat()
    out=Path("generated/sanctions"); out.mkdir(parents=True,exist_ok=True)
    cache=Path(".sanctions-cache"); cache.mkdir(parents=True,exist_ok=True)

    un_url="https://scsanctions.un.org/resources/xml/en/name/consolidated.xml"
    uk_url="https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv"

    un_resp=get(un_url,timeout=180)
    uk_resp=get(uk_url,timeout=180)
    current={
        "unsc":parse_un_consolidated_xml(un_resp.payload,collected_at=collected_at,source_url=un_resp.url),
        "uk":parse_uk_csv(uk_resp.payload,collected_at=collected_at,source_url=uk_resp.url),
    }
    urls={"unsc":un_resp.url,"uk":uk_resp.url}
    diffs={}; counts={}
    for key,rows in current.items():
        previous_path=cache/f"{key}.json"
        previous=_load_previous(previous_path)
        snap=_snapshot(out/f"{key}.json",rows,source_url=urls[key])
        (out/f"{key}.json").write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding="utf-8")
        diffs[key]=diff_designations(previous,rows) if previous else {
            "added":[],"removed":[],"modified":[],"unchanged":0,
            "baseline_snapshot":True,
            "legal_effect_requires_authority_specific_review":True,
        }
        counts[key]=len(rows)
        previous_path.write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding="utf-8")

    diff_payload={
        "schema_version":"geowatch-sanctions-diff-bundle-v1",
        "collected_at":collected_at,
        "diffs":diffs,
        "governance":{
            "official_designation_record_only":True,
            "legal_effect_requires_jurisdiction_specific_review":True,
            "designation_not_conflict_event_evidence":True,
            "ofac_automation_pending_validated_export_endpoint":True,
        },
    }
    (out/"diff.json").write_text(json.dumps(diff_payload,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={
        "schema_version":"geowatch-sanctions-build-summary-v1",
        "collected_at":collected_at,
        "counts":counts,
        "changes":{
            key:{
                "added":len(value.get("added",[])),"removed":len(value.get("removed",[])),"modified":len(value.get("modified",[])),
                "baseline_snapshot":bool(value.get("baseline_snapshot",False)),
            }
            for key,value in diffs.items()
        },
        "ofac_status":"registry_only_until_concrete_SLS_export_or_API_endpoint_is_validated",
    }
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

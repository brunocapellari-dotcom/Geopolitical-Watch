from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

from .http import get


def load_registry(path: str | Path = "config/operations/ucdp_bulk.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def download_rows(source_key: str, *, registry_path: str | Path = "config/operations/ucdp_bulk.json", timeout: int = 180) -> tuple[list[dict], str]:
    registry = load_registry(registry_path)
    url = registry["sources"][source_key]
    response = get(url, timeout=timeout)
    content_type = (response.content_type or "").casefold()
    if url.casefold().endswith(".zip") or "zip" in content_type:
        rows = read_zip_csv(response.payload)
    else:
        rows = read_csv(response.payload)
    return rows, response.url


def read_csv(payload: bytes) -> list[dict]:
    text = payload.decode("utf-8-sig", errors="replace")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def read_zip_csv(payload: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        candidates = [name for name in archive.namelist() if name.casefold().endswith(".csv") and not name.startswith("__MACOSX/")]
        if not candidates:
            raise ValueError("UCDP ZIP contains no CSV file")
        candidates.sort(key=lambda name: ("codebook" in name.casefold(), len(name), name))
        return read_csv(archive.read(candidates[0]))


def aggregate_armed_conflict_cases(rows: list[dict]) -> list[dict]:
    """Aggregate UCDP/PRIO conflict-year rows into historical conflict cases.

    Column aliases make the parser tolerant to minor naming changes between UCDP
    releases. Output is structural historical data and does not assert current status.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        conflict_id = _pick(row, "conflict_id", "conflictid", "id", "ID")
        if conflict_id:
            groups[str(conflict_id)].append(row)
    cases = []
    for conflict_id, values in sorted(groups.items(), key=lambda item: item[0]):
        years = sorted({_int(_pick(row, "year", "Year")) for row in values if _int(_pick(row, "year", "Year")) is not None})
        if not years:
            continue
        sample = values[0]
        location = _pick(sample, "location", "Location") or "Unknown"
        side_a = _pick(sample, "side_a", "Side_A", "sidea")
        side_b = _pick(sample, "side_b", "Side_B", "sideb")
        region = _pick(sample, "region", "Region") or "Unknown"
        conflict_type = _pick(sample, "type_of_conflict", "type", "Type") or "unknown"
        start_date = _pick(sample, "start_date2", "startdate2", "Startdate2", "start_date", "startdate", "Startdate")
        cases.append({
            "case_id": f"ucdp_conflict_{conflict_id}",
            "ucdp_conflict_id": str(conflict_id),
            "start": _normalize_date(start_date) or f"{years[0]:04d}-01-01",
            "end": f"{years[-1]:04d}-12-31",
            "region": str(region),
            "location": str(location),
            "actors": [value for value in (side_a, side_b) if value],
            "types": [f"ucdp_type_{conflict_type}"],
            "outcome_tags": [],
            "source_ids": ["ucdp_prio_acd_26_1"],
            "dataset_version": "26.1",
            "date_precision": "dataset_year_or_startdate",
            "historical_context_not_current_evidence": True,
        })
    return cases


def aggregate_actor_profiles(rows: list[dict]) -> list[dict]:
    profiles = []
    for row in rows:
        actor_id = _pick(row, "actor_id", "ActorId", "actorid", "id", "ID")
        name = _pick(row, "name", "Name", "actor_name", "ActorName")
        if not actor_id or not name:
            continue
        aliases = _pick(row, "name_orig", "name_original", "aliases", "alias")
        profiles.append({
            "actor_id": f"UCDP_{actor_id}",
            "ucdp_actor_id": str(actor_id),
            "name": str(name),
            "actor_type": "ucdp_actor",
            "aliases_raw": str(aliases) if aliases else None,
            "source_ids": ["ucdp_actor_26_1"],
            "dataset_version": "26.1",
            "context_not_evidence": True,
        })
    return profiles


def termination_outcomes(rows: list[dict]) -> dict[str, dict]:
    outcome_map = {
        "1": "peace_agreement",
        "2": "ceasefire",
        "3": "victory_side_a",
        "4": "victory_side_b",
        "5": "low_activity",
        "6": "actor_ceases_to_exist",
    }
    result: dict[str, dict] = {}
    for row in rows:
        conflict_id = _pick(row, "ID", "id", "conflict_id", "ConflictId")
        if not conflict_id:
            continue
        outcome_raw = str(_pick(row, "Outcome", "outcome") or "").strip()
        enddate = _pick(row, "Enddate", "enddate", "end_date")
        result[str(conflict_id)] = {
            "outcome_tag": outcome_map.get(outcome_raw, f"termination_code_{outcome_raw}" if outcome_raw else None),
            "end": _normalize_date(enddate),
            "source_ids": ["ucdp_termination_4_2024"],
        }
    return result


def enrich_cases_with_termination(cases: list[dict], terminations: dict[str, dict]) -> list[dict]:
    enriched = []
    for case in cases:
        row = dict(case)
        termination = terminations.get(str(case.get("ucdp_conflict_id")))
        if termination:
            if termination.get("end"):
                row["end"] = termination["end"]
            if termination.get("outcome_tag"):
                row["outcome_tags"] = sorted(set(row.get("outcome_tags", [])) | {termination["outcome_tag"]})
            row["source_ids"] = sorted(set(row.get("source_ids", [])) | set(termination.get("source_ids", [])))
        enriched.append(row)
    return enriched


def _pick(row: dict, *names: str):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    folded = {str(key).casefold(): value for key, value in row.items()}
    for name in names:
        value = folded.get(name.casefold())
        if value not in (None, ""):
            return value
    return None


def _int(value):
    try:
        return int(float(str(value))) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _normalize_date(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace("/", "-")
    parts = text.split(" ", 1)[0].split("-")
    if len(parts) == 3:
        if len(parts[0]) == 4:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        if len(parts[2]) == 4:
            return f"{int(parts[2]):04d}-{int(parts[1]):02d}-{int(parts[0]):02d}"
    if len(text) >= 4 and text[:4].isdigit():
        return f"{int(text[:4]):04d}-01-01"
    return None

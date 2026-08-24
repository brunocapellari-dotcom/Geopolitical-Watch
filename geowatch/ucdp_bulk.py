from __future__ import annotations

import csv
import io
import json
import re
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
    """Convert UCDP/PRIO conflict-year observations into continuous conflict episodes.

    UCDP keeps the same ``conflict_id`` when the same incompatibility restarts after
    one or more inactive years. Geopolitical Watch therefore splits each conflict ID
    into continuous active-year episodes instead of incorrectly treating the entire
    1946-2025 history of an incompatibility as one episode.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        conflict_id = _pick(row, "conflict_id", "conflictid", "id")
        year = _int(_pick(row, "year"))
        if conflict_id and year is not None:
            groups[str(conflict_id)].append(row)

    cases: list[dict] = []
    for conflict_id, values in sorted(groups.items(), key=lambda item: item[0]):
        ordered = sorted(values, key=lambda row: (_int(_pick(row, "year")) or 0, str(_pick(row, "start_date2") or "")))
        sequences: list[list[dict]] = []
        current: list[dict] = []
        previous_year: int | None = None
        for row in ordered:
            year = _int(_pick(row, "year"))
            if year is None:
                continue
            if current and previous_year is not None and year > previous_year + 1:
                sequences.append(current)
                current = []
            current.append(row)
            previous_year = year
        if current:
            sequences.append(current)

        for episode_no, sequence in enumerate(sequences, start=1):
            years = [_int(_pick(row, "year")) for row in sequence]
            years = [year for year in years if year is not None]
            if not years:
                continue
            first = sequence[0]
            last = sequence[-1]
            start_date = _first_value(sequence, "start_date2", "start_date")
            ep_end = _int(_pick(last, "ep_end"))
            ep_end_date = _pick(last, "ep_end_date")
            ended = ep_end == 1
            actors = _unique_values(sequence, "side_a", "side_b")
            secondary_parties = _unique_values(sequence, "side_a_2nd", "side_b_2nd")
            conflict_types = sorted({str(value) for row in sequence if (value := _pick(row, "type_of_conflict")) not in (None, "")})
            intensity_levels = sorted({_int(_pick(row, "intensity_level")) for row in sequence if _int(_pick(row, "intensity_level")) is not None})
            start_precision = _int(_pick(first, "start_prec2", "start_prec"))
            end_precision = _int(_pick(last, "ep_end_prec")) if ended else None
            cases.append({
                "case_id": f"ucdp_conflict_{conflict_id}_episode_{episode_no}",
                "ucdp_conflict_id": conflict_id,
                "ucdp_episode_no": episode_no,
                "start": _normalize_date(start_date) or f"{years[0]:04d}-01-01",
                "end": (_normalize_date(ep_end_date) or f"{years[-1]:04d}-12-31") if ended else None,
                "active_year_start": years[0],
                "active_year_end": years[-1],
                "active_years": years,
                "active_at_dataset_end": not ended,
                "region": str(_pick(first, "region") or "Unknown"),
                "location": str(_pick(first, "location") or "Unknown"),
                "actors": actors,
                "secondary_parties": secondary_parties,
                "types": [f"ucdp_type_{value}" for value in conflict_types] or ["ucdp_type_unknown"],
                "intensity_levels": intensity_levels,
                "outcome_tags": [],
                "source_ids": ["ucdp_prio_acd_26_1"],
                "dataset_version": str(_pick(first, "version") or "26.1"),
                "date_precision": {
                    "start_prec": start_precision,
                    "end_prec": end_precision,
                    "ucdp_precision_codes_preserved": True,
                },
                "historical_context_not_current_evidence": True,
            })
    return cases


def aggregate_actor_profiles(rows: list[dict]) -> list[dict]:
    """Normalize the real UCDP Actor Dataset 26.1 schema.

    ``NameData`` is the canonical name used in current UCDP data. Historical and
    renamed forms are preserved as aliases. Splinter/alliance/join relations are
    exposed as lineage metadata rather than inferred from names.
    """
    profiles = []
    for row in rows:
        actor_id = _pick(row, "ActorId", "actor_id", "actorid", "id")
        name = _pick(row, "NameData", "name_data", "Name", "name")
        if not actor_id or not name:
            continue
        alias_fields = (
            "NameOrig", "NameOrigFull", "NameOrigFullEng", "NewName",
            "NewNameFullMotherTongue", "NewNameFullEng", "NamePrev",
            "NameSplitTemp", "NameAlliance", "GroupName",
        )
        aliases = []
        seen = {str(name).strip().casefold()}
        for field in alias_fields:
            value = _pick(row, field)
            if value:
                for alias in _split_list(value):
                    key = alias.casefold()
                    if key not in seen:
                        seen.add(key)
                        aliases.append(alias)
        profiles.append({
            "actor_id": f"UCDP_{actor_id}",
            "ucdp_actor_id": str(actor_id),
            "name": str(name).strip(),
            "actor_type": "ucdp_actor",
            "aliases": aliases,
            "organization_level": _int(_pick(row, "Org")),
            "locations": _split_list(_pick(row, "Location")),
            "regions_raw": _split_list(_pick(row, "Region")),
            "conflict_ids": _split_list(_pick(row, "ConflictId")),
            "dyad_ids": _split_list(_pick(row, "DyadId")),
            "primary_party": _bool01(_pick(row, "PrimaryParty")),
            "lineage": {
                "splinter": _bool01(_pick(row, "Splinter")),
                "parent_actor_id": _string_or_none(_pick(row, "ActorIdPrev")),
                "temporary_split": _bool01(_pick(row, "SplitTemp")),
                "temporary_split_parent_actor_id": _string_or_none(_pick(row, "ActorIdSplitTemp")),
                "alliance_created": _bool01(_pick(row, "Alliance")),
                "alliance_actor_id": _string_or_none(_pick(row, "ActorIdAlliance")),
                "joined_existing_group": _bool01(_pick(row, "JoinGroup")),
                "joined_actor_id": _string_or_none(_pick(row, "ActorIdGroup")),
            },
            "source_ids": ["ucdp_actor_26_1"],
            "dataset_version": str(_pick(row, "Version") or "26.1"),
            "context_not_evidence": True,
        })
    return profiles


def termination_outcomes(rows: list[dict]) -> dict[tuple[str, int], dict]:
    """Normalize conflict-level UCDP Conflict Termination Dataset v4-2024 rows.

    The current codebook uses conflict-level fields such as ``c_epno``,
    ``c_outcome`` and ``c_ependdate``. Keys include episode number so repeated
    episodes of the same conflict are never overwritten.
    """
    outcome_map = {
        "1": "peace_agreement",
        "2": "ceasefire",
        "3": "victory_side_a",
        "4": "victory_side_b",
        "5": "low_activity",
        "6": "actor_ceases_to_exist",
    }
    result: dict[tuple[str, int], dict] = {}
    for row in rows:
        conflict_id = _pick(row, "conflict_id", "conflictid", "ID", "id")
        episode_no = _int(_pick(row, "c_epno", "cepno", "episode_no"))
        if not conflict_id or episode_no is None:
            continue
        outcome_raw = str(_pick(row, "c_outcome", "coutcome", "Outcome", "outcome") or "").strip()
        enddate = _pick(row, "c_ependdate", "cependdate", "Enddate", "enddate", "end_date")
        endprec = _int(_pick(row, "c_ependprec", "cependprec"))
        result[(str(conflict_id), episode_no)] = {
            "outcome_tag": outcome_map.get(outcome_raw, f"termination_code_{outcome_raw}" if outcome_raw else None),
            "end": _normalize_date(enddate),
            "end_precision": endprec,
            "source_ids": ["ucdp_termination_4_2024"],
            "termination_dataset_version": str(_pick(row, "version") or "4-2024"),
        }
    return result


def enrich_cases_with_termination(cases: list[dict], terminations: dict[tuple[str, int], dict]) -> list[dict]:
    enriched = []
    for case in cases:
        row = dict(case)
        key = (str(case.get("ucdp_conflict_id")), int(case.get("ucdp_episode_no") or 0))
        termination = terminations.get(key)
        if termination:
            if termination.get("end"):
                row["end"] = termination["end"]
                row["active_at_dataset_end"] = False
            if termination.get("outcome_tag"):
                row["outcome_tags"] = sorted(set(row.get("outcome_tags", [])) | {termination["outcome_tag"]})
            row["source_ids"] = sorted(set(row.get("source_ids", [])) | set(termination.get("source_ids", [])))
            row["termination_end_precision"] = termination.get("end_precision")
            row["termination_dataset_version"] = termination.get("termination_dataset_version")
        enriched.append(row)
    return enriched


def _pick(row: dict, *names: str):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    normalized = {_keynorm(key): value for key, value in row.items()}
    for name in names:
        value = normalized.get(_keynorm(name))
        if value not in (None, ""):
            return value
    return None


def _keynorm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _first_value(rows: list[dict], *names: str):
    for row in rows:
        value = _pick(row, *names)
        if value not in (None, ""):
            return value
    return None


def _unique_values(rows: list[dict], *names: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in names:
            raw = _pick(row, name)
            for item in _split_list(raw):
                key = item.casefold()
                if key not in seen:
                    seen.add(key)
                    values.append(item)
    return values


def _split_list(value) -> list[str]:
    if value in (None, ""):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _string_or_none(value) -> str | None:
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


def _bool01(value) -> bool | None:
    if value in (None, ""):
        return None
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
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
        try:
            if len(parts[0]) == 4:
                return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
            if len(parts[2]) == 4:
                return f"{int(parts[2]):04d}-{int(parts[1]):02d}-{int(parts[0]):02d}"
        except ValueError:
            return None
    if len(text) >= 4 and text[:4].isdigit():
        return f"{int(text[:4]):04d}-01-01"
    return None

from __future__ import annotations

from collections import defaultdict


def derive_conflict_identity_labels(rows: list[dict], *, max_positive: int = 500, max_negative: int = 500) -> list[dict]:
    """Derive dataset-identity labels from UCDP conflict-year rows.

    These are useful deterministic validation labels, but are explicitly not human
    adjudicated episode gold labels. Same UCDP conflict ID => positive identity label;
    different conflict IDs in the same location/year => hard negative candidate.
    """
    by_conflict: dict[str, list[dict]] = defaultdict(list)
    by_location_year: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        cid = _pick(row, "conflict_id", "conflictid", "ID", "id")
        year = _pick(row, "year", "Year")
        location = _pick(row, "location", "Location")
        if not cid:
            continue
        by_conflict[str(cid)].append(row)
        if year and location:
            by_location_year[(str(location), str(year))].append(row)
    labels: list[dict] = []
    positives = 0
    for cid, group in sorted(by_conflict.items()):
        ordered = sorted(group, key=lambda r: str(_pick(r, "year", "Year") or ""))
        for left, right in zip(ordered, ordered[1:]):
            if positives >= max_positive:
                break
            labels.append({
                "label_id": f"ucdp_same:{cid}:{_pick(left,'year','Year')}:{_pick(right,'year','Year')}",
                "left_conflict_id": cid,
                "right_conflict_id": cid,
                "same_conflict": True,
                "left_year": _pick(left, "year", "Year"),
                "right_year": _pick(right, "year", "Year"),
                "location": _pick(left, "location", "Location"),
                "label_source": "ucdp_conflict_id",
                "human_gold": False,
            })
            positives += 1
        if positives >= max_positive:
            break
    negatives = 0
    for (location, year), group in sorted(by_location_year.items()):
        cids = sorted({str(_pick(row, "conflict_id", "conflictid", "ID", "id")) for row in group if _pick(row, "conflict_id", "conflictid", "ID", "id")})
        for i in range(len(cids)):
            for j in range(i + 1, len(cids)):
                if negatives >= max_negative:
                    break
                labels.append({
                    "label_id": f"ucdp_diff:{location}:{year}:{cids[i]}:{cids[j]}",
                    "left_conflict_id": cids[i],
                    "right_conflict_id": cids[j],
                    "same_conflict": False,
                    "left_year": year,
                    "right_year": year,
                    "location": location,
                    "label_source": "ucdp_distinct_conflict_ids_same_location_year",
                    "human_gold": False,
                })
                negatives += 1
            if negatives >= max_negative:
                break
        if negatives >= max_negative:
            break
    return labels


def label_summary(labels: list[dict]) -> dict:
    return {
        "schema_version": "geowatch-ucdp-identity-label-summary-v1",
        "label_count": len(labels),
        "positive": sum(1 for row in labels if row.get("same_conflict")),
        "negative": sum(1 for row in labels if not row.get("same_conflict")),
        "human_gold": False,
        "purpose": "pre-gold deterministic validation and error discovery",
    }


def _pick(row: dict, *names: str):
    folded = {str(k).casefold(): v for k, v in row.items()}
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
        value = folded.get(name.casefold())
        if value not in (None, ""):
            return value
    return None

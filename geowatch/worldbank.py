from __future__ import annotations

import json
from pathlib import Path

from .http import get


def load_registry(path: str | Path = "config/operations/worldbank.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def countries(*, registry_path: str | Path = "config/operations/worldbank.json", timeout: int = 120) -> tuple[list[dict], str]:
    registry = load_registry(registry_path)
    response = get(registry["country_endpoint"], query={"format":"json","per_page":400}, timeout=timeout)
    body = json.loads(response.payload.decode("utf-8"))
    rows = body[1] if isinstance(body, list) and len(body) > 1 and isinstance(body[1], list) else []
    values = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        region = row.get("region") or {}
        # World Bank aggregates have region id NA; keep them out of country profiles.
        if str(region.get("id") or "") == "NA":
            continue
        values.append({
            "country_id": row.get("id"),
            "iso2": row.get("iso2Code"),
            "name": row.get("name"),
            "region": region.get("value"),
            "income_level": (row.get("incomeLevel") or {}).get("value"),
            "lending_type": (row.get("lendingType") or {}).get("value"),
            "capital_city": row.get("capitalCity") or None,
            "longitude": _float(row.get("longitude")),
            "latitude": _float(row.get("latitude")),
            "source_ids": ["world_bank_country_api"],
            "context_not_evidence": True,
        })
    return values, response.url


def indicator(indicator_id: str, *, start_year: int, end_year: int, registry_path: str | Path = "config/operations/worldbank.json", timeout: int = 120) -> tuple[list[dict], str]:
    registry = load_registry(registry_path)
    endpoint = registry["indicator_endpoint"].format(indicator=indicator_id)
    response = get(endpoint, query={"format":"json","per_page":20000,"date":f"{start_year}:{end_year}"}, timeout=timeout)
    body = json.loads(response.payload.decode("utf-8"))
    rows = body[1] if isinstance(body, list) and len(body) > 1 and isinstance(body[1], list) else []
    observations = []
    for row in rows:
        if not isinstance(row, dict) or row.get("value") is None:
            continue
        country = row.get("country") or {}
        country_id = row.get("countryiso3code") or country.get("id")
        if not country_id:
            continue
        observations.append({
            "country_id": country_id,
            "country_name": country.get("value"),
            "indicator_id": indicator_id,
            "reference_year": int(row["date"]) if str(row.get("date") or "").isdigit() else row.get("date"),
            "value": row.get("value"),
            "unit": row.get("unit") or None,
            "obs_status": row.get("obs_status") or None,
            "decimal": row.get("decimal"),
            "source_ids": ["world_bank_indicators_api"],
            "evidence_class": "observed_statistical_series",
            "not_conflict_event_evidence": True,
        })
    return observations, response.url


def latest_by_country(observations: list[dict]) -> list[dict]:
    latest: dict[tuple[str,str], dict] = {}
    for row in observations:
        key = (str(row.get("country_id")), str(row.get("indicator_id")))
        year = row.get("reference_year")
        prev = latest.get(key)
        if prev is None or str(year) > str(prev.get("reference_year")):
            latest[key] = row
    return sorted(latest.values(), key=lambda row: (str(row.get("country_id")), str(row.get("indicator_id"))))


def _float(value):
    try:
        text = str(value or "").strip()
        return float(text) if text else None
    except ValueError:
        return None

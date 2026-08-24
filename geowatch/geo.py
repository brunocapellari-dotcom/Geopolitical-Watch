from __future__ import annotations

import math
import unicodedata
from dataclasses import replace
from typing import Mapping

from .models import Event

# Seed aliases cover the most common alternate names seen in conflict/public-source feeds.
# Unknown names pass through after whitespace normalization; deployments may extend this
# mapping from configuration without changing the package.
DEFAULT_COUNTRY_ALIASES: dict[str, str] = {
    "usa": "United States",
    "u s": "United States",
    "u s a": "United States",
    "united states of america": "United States",
    "russian federation": "Russia",
    "state of palestine": "Palestine",
    "palestinian territories": "Palestine",
    "occupied palestinian territory": "Palestine",
    "islamic republic of iran": "Iran",
    "syrian arab republic": "Syria",
    "turkey": "Türkiye",
    "turkiye": "Türkiye",
    "democratic republic of the congo": "Democratic Republic of the Congo",
    "congo democratic republic of the": "Democratic Republic of the Congo",
    "dr congo": "Democratic Republic of the Congo",
    "drc": "Democratic Republic of the Congo",
    "republic of the congo": "Republic of the Congo",
    "democratic peoples republic of korea": "North Korea",
    "dprk": "North Korea",
    "north korea": "North Korea",
    "republic of korea": "South Korea",
    "south korea": "South Korea",
    "burma": "Myanmar",
    "ivory coast": "Côte d’Ivoire",
    "cote d ivoire": "Côte d’Ivoire",
    "cape verde": "Cabo Verde",
    "swaziland": "Eswatini",
    "lao peoples democratic republic": "Laos",
    "viet nam": "Vietnam",
    "czech republic": "Czechia",
    "moldova republic of": "Moldova",
    "bolivia plurinational state of": "Bolivia",
    "venezuela bolivarian republic of": "Venezuela",
    "tanzania united republic of": "Tanzania",
}


def normalize_country(value: str | None, aliases: Mapping[str, str] | None = None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    if not cleaned:
        return None
    merged = dict(DEFAULT_COUNTRY_ALIASES)
    if aliases:
        for key, canonical in aliases.items():
            merged[_alias_key(key)] = canonical
    key = _alias_key(cleaned)
    if key in merged:
        return merged[key]
    return cleaned


def canonicalize_event(event: Event, aliases: Mapping[str, str] | None = None) -> Event:
    canonical = normalize_country(event.country, aliases)
    if canonical == event.country:
        return event
    return replace(event, country=canonical)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(a)))


def _alias_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    chars = [ch.casefold() if ch.isalnum() else " " for ch in ascii_text]
    return " ".join("".join(chars).split())

from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from .models import Event, EvidenceRef

_WIRE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("reuters", ("reuters",)),
    ("associated_press", ("associated press", "ap news", "apnews")),
    ("afp", ("agence france-presse", "agence france presse", "afp")),
    ("tass", ("tass",)),
    ("xinhua", ("xinhua",)),
)

_WORDS = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def independent_source_count(
    evidence: list[EvidenceRef],
    events: dict[str, Event],
) -> int:
    """Return a conservative count of independent reporting groups.

    Different publishers are not automatically independent. Evidence is grouped
    when it shares the same provider/origin, an explicit wire-service origin, or
    a near-identical headline that is consistent with syndication/copy-paste.
    """
    return len(source_dependency_groups(evidence, events))


def source_dependency_groups(
    evidence: list[EvidenceRef],
    events: dict[str, Event],
) -> tuple[tuple[str, ...], ...]:
    if not evidence:
        return ()

    parent = list(range(len(evidence)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    providers = [_provider_key(row, events.get(row.event_id)) for row in evidence]
    wires = [_wire_key(row, events.get(row.event_id)) for row in evidence]
    titles = [_headline(events.get(row.event_id)) for row in evidence]

    for left in range(len(evidence)):
        for right in range(left + 1, len(evidence)):
            if providers[left] and providers[left] == providers[right]:
                union(left, right)
                continue
            if wires[left] and wires[left] == wires[right]:
                union(left, right)
                continue
            if (
                evidence[left].verification_level in {"osint_signal", "curated_report"}
                and evidence[right].verification_level in {"osint_signal", "curated_report"}
                and _near_duplicate(titles[left], titles[right])
            ):
                union(left, right)

    groups: dict[int, list[str]] = {}
    for index, row in enumerate(evidence):
        groups.setdefault(find(index), []).append(row.evidence_id)
    return tuple(tuple(sorted(ids)) for _, ids in sorted(groups.items()))


def _provider_key(evidence: EvidenceRef, event: Event | None) -> str:
    value = evidence.provider or (event.publisher if event else None)
    if value:
        normalized = _normalize_provider(value)
        if normalized:
            return normalized
    for url in (evidence.url, event.source_url if event else None):
        if not url:
            continue
        try:
            host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
        except ValueError:
            host = ""
        if host:
            return host
    return evidence.source_id.strip().casefold()


def _wire_key(evidence: EvidenceRef, event: Event | None) -> str | None:
    parts = [
        evidence.provider or "",
        evidence.url or "",
        event.publisher if event else "",
        event.source_url if event else "",
        event.title if event else "",
    ]
    haystack = " ".join(part for part in parts if part).casefold()
    for wire, markers in _WIRE_MARKERS:
        if any(_marker_present(haystack, marker) for marker in markers):
            return f"wire:{wire}"
    return None


def _headline(event: Event | None) -> str:
    return _normalize_text(event.title if event else "")


def _near_duplicate(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    left_tokens = left.split()
    right_tokens = right.split()
    if min(len(left_tokens), len(right_tokens)) < 5:
        return False
    sequence = SequenceMatcher(None, left, right).ratio()
    left_set, right_set = set(left_tokens), set(right_tokens)
    union = left_set | right_set
    jaccard = len(left_set & right_set) / len(union) if union else 0.0
    return sequence >= 0.94 or jaccard >= 0.90


def _normalize_provider(value: str) -> str:
    text = value.strip().casefold()
    if "://" in text:
        try:
            text = (urlsplit(text).hostname or text).casefold()
        except ValueError:
            pass
    return text.removeprefix("www.").rstrip(".")


def _normalize_text(value: str) -> str:
    return " ".join(_WORDS.findall(value.casefold()))


def _marker_present(haystack: str, marker: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", haystack) is not None

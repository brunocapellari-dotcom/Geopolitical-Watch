from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .core import normalize_text

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid",
    "ref", "ref_src", "igshid",
}
_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


@dataclass(frozen=True)
class DedupFingerprint:
    canonical_url: str | None
    content_sha256: str
    normalized_text_sha256: str
    token_signature: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["token_signature"] = list(self.token_signature)
        return row


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url.strip())
    if parts.scheme.casefold() not in {"http", "https"} or not parts.hostname:
        return None
    host = parts.hostname.casefold().rstrip(".")
    port = parts.port
    netloc = host
    if port and not ((parts.scheme.casefold() == "http" and port == 80) or (parts.scheme.casefold() == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_KEYS
        and not any(key.casefold().startswith(prefix) for prefix in _TRACKING_PREFIXES)
    ]
    query.sort()
    return urlunsplit((parts.scheme.casefold(), netloc, path, urlencode(query), ""))


def fingerprint_content(payload: bytes, *, text: str, url: str | None = None) -> DedupFingerprint:
    normalized = normalize_text(text)
    tokens = tuple(sorted(set(_TOKEN_RE.findall(normalized))))
    return DedupFingerprint(
        canonical_url=canonicalize_url(url),
        content_sha256=hashlib.sha256(payload).hexdigest(),
        normalized_text_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        token_signature=tokens,
    )


def text_similarity(left: str, right: str) -> float:
    a = set(_TOKEN_RE.findall(normalize_text(left)))
    b = set(_TOKEN_RE.findall(normalize_text(right)))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def duplicate_reason(
    left: DedupFingerprint,
    right: DedupFingerprint,
    *,
    left_text: str | None = None,
    right_text: str | None = None,
    similarity_threshold: float = 0.92,
) -> str | None:
    if left.content_sha256 == right.content_sha256:
        return "identical_raw"
    if left.normalized_text_sha256 == right.normalized_text_sha256:
        return "identical_normalized_text"
    if left.canonical_url and left.canonical_url == right.canonical_url:
        return "canonical_url_match"
    if left_text is not None and right_text is not None and text_similarity(left_text, right_text) >= similarity_threshold:
        return "near_duplicate_text"
    return None

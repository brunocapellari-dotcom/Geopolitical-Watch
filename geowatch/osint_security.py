from __future__ import annotations

import hashlib
import html
import ipaddress
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid",
    "ref_src", "ref_url", "vero_conv", "vero_id",
}
_TRACKING_PREFIXES = ("utm_", "pk_", "mtm_", "ga_")
_BLOCKED_TAGS = {"script", "style", "iframe", "object", "embed", "form", "svg", "math", "template"}
_PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "developer message",
    "execute this command",
    "run this command",
    "reveal credentials",
    "reveal your secret",
    "tool call",
)


@dataclass(frozen=True)
class UntrustedContent:
    source_id: str
    collected_at: str
    content_sha256: str
    original_bytes: int
    sanitized_text: str
    suspicious_instruction_markers: tuple[str, ...]
    trust_label: str = "HOSTILE_UNTRUSTED"
    executable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "collected_at": self.collected_at,
            "content_sha256": self.content_sha256,
            "original_bytes": self.original_bytes,
            "sanitized_text": self.sanitized_text,
            "suspicious_instruction_markers": list(self.suspicious_instruction_markers),
            "trust_label": self.trust_label,
            "executable": self.executable,
        }


class _TextOnlyHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        if tag.casefold() in _BLOCKED_TAGS:
            self._blocked_depth += 1

    def handle_startendtag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        return

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in _BLOCKED_TAGS and self._blocked_depth:
            self._blocked_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._blocked_depth:
            self.parts.append(data)


def sanitize_untrusted_html(payload: bytes | str, *, max_chars: int = 250_000) -> str:
    text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload)
    parser = _TextOnlyHTMLParser()
    parser.feed(text[: max_chars * 4])
    parser.close()
    clean = html.unescape(" ".join(parser.parts))
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_chars]


def wrap_untrusted_content(
    payload: bytes,
    *,
    source_id: str,
    collected_at: str,
    content_type: str | None = None,
    max_chars: int = 250_000,
) -> UntrustedContent:
    kind = (content_type or "").casefold()
    if "html" in kind or payload.lstrip()[:1] == b"<":
        sanitized = sanitize_untrusted_html(payload, max_chars=max_chars)
    else:
        sanitized = payload.decode("utf-8", errors="replace")[:max_chars]
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", sanitized)
    folded = sanitized.casefold()
    markers = tuple(sorted(marker for marker in _PROMPT_INJECTION_MARKERS if marker in folded))
    return UntrustedContent(
        source_id=source_id,
        collected_at=collected_at,
        content_sha256=hashlib.sha256(payload).hexdigest(),
        original_bytes=len(payload),
        sanitized_text=sanitized,
        suspicious_instruction_markers=markers,
    )


def sanitize_tracking_url(url: str) -> str:
    parts = _validate_external_url(url)
    pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        folded = key.casefold()
        if folded in _TRACKING_KEYS or any(folded.startswith(prefix) for prefix in _TRACKING_PREFIXES):
            continue
        pairs.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), ""))


def validate_collector_url(url: str, *, allowed_hosts: set[str] | frozenset[str] | None = None) -> str:
    parts = _validate_external_url(url)
    hostname = (parts.hostname or "").casefold().rstrip(".")
    if allowed_hosts is not None:
        allowed = {item.casefold().rstrip(".") for item in allowed_hosts}
        if hostname not in allowed:
            raise ValueError("collector URL host is not on the source allowlist")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def safe_download_metadata(
    payload: bytes,
    *,
    source_id: str,
    source_url: str,
    collected_at: str,
    max_bytes: int = 25 * 1024 * 1024,
) -> dict[str, object]:
    if len(payload) > max_bytes:
        raise ValueError("download exceeds quarantine size limit")
    clean_url = sanitize_tracking_url(source_url)
    return {
        "source_id": source_id,
        "source_url": clean_url,
        "collected_at": collected_at,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "quarantine_required": True,
        "executable": False,
        "open_in_main_runtime": False,
    }


def _validate_external_url(url: str):  # type: ignore[no-untyped-def]
    value = str(url or "").strip()
    parts = urlsplit(value)
    if parts.scheme.casefold() not in {"http", "https"}:
        raise ValueError("only HTTP(S) external URLs are allowed")
    if not parts.hostname:
        raise ValueError("URL hostname is required")
    if parts.username is not None or parts.password is not None:
        raise ValueError("credentials embedded in URLs are forbidden")
    hostname = parts.hostname.casefold().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        raise ValueError("local addresses are forbidden")
    try:
        ip = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        ip = None
    if ip is not None and (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("non-public IP addresses are forbidden")
    return parts

from __future__ import annotations

import hashlib
import ipaddress
import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HttpResponse:
    payload: bytes
    url: str
    content_type: str | None
    headers: tuple[tuple[str, str], ...] = ()


_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_ALLOWED_WEB_SCHEMES = {"http", "https"}


def validate_web_url(url: str, *, require_https: bool = False) -> str:
    """Reject local-file/custom schemes before any urllib network operation.

    URLs in this project come from reviewed source configuration or fixed provider
    bases. This validation is still applied centrally so a future configuration
    mistake cannot turn the HTTP helper into a file/custom-scheme reader.
    """
    value = str(url or "").strip()
    parts = urlsplit(value)
    allowed = {"https"} if require_https else _ALLOWED_WEB_SCHEMES
    if parts.scheme.casefold() not in allowed:
        raise ValueError("URL scheme is not allowed")
    if not parts.hostname:
        raise ValueError("URL hostname is required")
    if parts.username is not None or parts.password is not None:
        raise ValueError("credentials in URL are not allowed")
    hostname = parts.hostname.casefold().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        raise ValueError("local addresses are not allowed")
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
        raise ValueError("non-public IP addresses are not allowed")
    return value


def get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    query: dict[str, str | int] | None = None,
    retries: int = 2,
    backoff_seconds: float = 1.0,
    max_backoff_seconds: float = 30.0,
) -> HttpResponse:
    url = validate_web_url(url)
    if query:
        parts = urlsplit(url)
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        pairs.extend((key, str(value)) for key, value in query.items())
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))
    req_headers = {"User-Agent": "GeopoliticalWatch/0.14"}
    req_headers.update(headers or {})
    request = Request(url, headers=req_headers)

    attempts = max(0, int(retries)) + 1
    for attempt in range(attempts):
        try:
            # B310 is mitigated by validate_web_url immediately above; only
            # http/https with a hostname and no URL credentials are permitted.
            with urlopen(request, timeout=timeout) as response:  # nosec B310
                final_url = validate_web_url(response.geturl())
                return HttpResponse(
                    response.read(),
                    final_url,
                    response.headers.get("Content-Type"),
                    safe_response_headers(response.headers),
                )
        except HTTPError as exc:
            if exc.code not in _RETRYABLE_HTTP_CODES or attempt >= attempts - 1:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = _retry_delay(attempt, retry_after, backoff_seconds, url=url, max_backoff_seconds=max_backoff_seconds)
            time.sleep(delay)
        except URLError:
            if attempt >= attempts - 1:
                raise
            time.sleep(_retry_delay(attempt, None, backoff_seconds, url=url, max_backoff_seconds=min(15.0, max_backoff_seconds)))
    raise RuntimeError("HTTP retry loop exhausted unexpectedly")


def post_form(url: str, data: dict[str, str], *, headers: dict[str, str] | None = None, timeout: int = 60) -> HttpResponse:
    url = validate_web_url(url)
    payload = urlencode(data).encode("utf-8")
    req_headers = {
        "User-Agent": "GeopoliticalWatch/0.14",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    req_headers.update(headers or {})
    request = Request(url, data=payload, headers=req_headers, method="POST")
    # B310 is mitigated by validate_web_url above and final redirect validation.
    with urlopen(request, timeout=timeout) as response:  # nosec B310
        final_url = validate_web_url(response.geturl())
        return HttpResponse(
            response.read(),
            final_url,
            response.headers.get("Content-Type"),
            safe_response_headers(response.headers),
        )


def json_body(response: HttpResponse) -> dict:
    return json.loads(response.payload.decode("utf-8"))


def _retry_delay(attempt: int, retry_after: str | None, backoff_seconds: float, *, url: str = "", max_backoff_seconds: float = 30.0) -> float:
    if retry_after:
        try:
            return min(max_backoff_seconds, max(0.0, float(retry_after)))
        except ValueError:
            pass
    base = max(0.0, backoff_seconds) * (2 ** attempt)
    digest = hashlib.sha256(f"{url}|{attempt}".encode()).digest()
    jitter_fraction = int.from_bytes(digest[:2], "big") / 65535.0
    jitter = base * 0.35 * jitter_fraction
    return min(max_backoff_seconds, base + jitter)


_SAFE_RESPONSE_HEADER_NAMES = {
    "cache-control",
    "content-language",
    "content-length",
    "content-type",
    "date",
    "etag",
    "expires",
    "last-modified",
}


def safe_response_headers(headers) -> tuple[tuple[str, str], ...]:  # type: ignore[no-untyped-def]
    values: list[tuple[str, str]] = []
    items = headers.items() if hasattr(headers, "items") else headers
    for key, value in items:
        name = str(key).strip().casefold()
        if name in _SAFE_RESPONSE_HEADER_NAMES:
            values.append((name, str(value).strip()[:2000]))
    return tuple(sorted(values))

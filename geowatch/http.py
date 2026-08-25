from __future__ import annotations

import hashlib
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


_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


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
            with urlopen(request, timeout=timeout) as response:
                return HttpResponse(response.read(), response.geturl(), response.headers.get("Content-Type"))
        except HTTPError as exc:
            if exc.code not in _RETRYABLE_HTTP_CODES or attempt >= attempts - 1:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = _retry_delay(attempt, retry_after, backoff_seconds, url=url, max_backoff_seconds=max_backoff_seconds)
            time.sleep(delay)
        except URLError:
            if attempt >= attempts - 1:
                raise
            time.sleep(_retry_delay(attempt, None, backoff_seconds, url=url, max_backoff_seconds=min(15.0,max_backoff_seconds)))
    raise RuntimeError("HTTP retry loop exhausted unexpectedly")


def post_form(url: str, data: dict[str, str], *, headers: dict[str, str] | None = None, timeout: int = 60) -> HttpResponse:
    payload = urlencode(data).encode("utf-8")
    req_headers = {
        "User-Agent": "GeopoliticalWatch/0.14",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    req_headers.update(headers or {})
    request = Request(url, data=payload, headers=req_headers, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return HttpResponse(response.read(), response.geturl(), response.headers.get("Content-Type"))


def json_body(response: HttpResponse) -> dict:
    return json.loads(response.payload.decode("utf-8"))


def _retry_delay(attempt: int, retry_after: str | None, backoff_seconds: float, *, url: str="", max_backoff_seconds: float=30.0) -> float:
    if retry_after:
        try:
            return min(max_backoff_seconds, max(0.0, float(retry_after)))
        except ValueError:
            pass
    base=max(0.0,backoff_seconds)*(2 ** attempt)
    digest=hashlib.sha256(f"{url}|{attempt}".encode()).digest()
    jitter_fraction=int.from_bytes(digest[:2],"big")/65535.0
    jitter=base*0.35*jitter_fraction
    return min(max_backoff_seconds,base+jitter)

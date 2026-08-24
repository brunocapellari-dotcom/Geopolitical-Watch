from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HttpResponse:
    payload: bytes
    url: str
    content_type: str | None


def get(url: str, *, headers: dict[str, str] | None = None, timeout: int = 60, query: dict[str, str | int] | None = None) -> HttpResponse:
    if query:
        parts = urlsplit(url)
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        pairs.extend((key, str(value)) for key, value in query.items())
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))
    req_headers = {"User-Agent": "GeopoliticalWatch/0.4"}
    req_headers.update(headers or {})
    request = Request(url, headers=req_headers)
    with urlopen(request, timeout=timeout) as response:
        return HttpResponse(response.read(), response.geturl(), response.headers.get("Content-Type"))


def json_body(response: HttpResponse) -> dict:
    return json.loads(response.payload.decode("utf-8"))

from __future__ import annotations

import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SENSITIVE_NAME_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "MAP_KEY", "ACCESS_KEY", "PRIVATE_KEY")
_SENSITIVE_QUERY_KEYS = {
    "key", "api_key", "apikey", "token", "access_token", "auth", "authorization",
    "password", "secret", "client_secret",
}


def redact_runtime_secrets(value: object) -> str:
    text = str(value)
    secrets = []
    for name, secret in os.environ.items():
        upper = name.upper()
        if not any(marker in upper for marker in _SENSITIVE_NAME_MARKERS):
            continue
        if secret and len(secret) >= 6:
            secrets.append(secret)
    for secret in sorted(set(secrets), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def redact_url(url: str, *, secret_path_values: tuple[str, ...] = ()) -> str:
    """Return a provenance-safe URL with credentials and known secrets removed."""
    text = redact_runtime_secrets(url)
    for secret in secret_path_values:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    parts = urlsplit(text)
    host = parts.hostname or ""
    netloc = host
    if parts.port:
        netloc = f"{host}:{parts.port}"
    pairs = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        if key.casefold() in _SENSITIVE_QUERY_KEYS or re.search(r"(?:token|secret|password|api.?key)", key, re.I):
            pairs.append((key, "[REDACTED]"))
        else:
            pairs.append((key, redact_runtime_secrets(val)))
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(pairs), ""))

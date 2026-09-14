from __future__ import annotations

import base64
import hashlib
import hmac
import html
import time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

_COOKIE = "geowatch_session"
_SESSION_SECONDS = 12 * 60 * 60


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _signature(secret: str, expires: int) -> str:
    return _b64(hmac.new(secret.encode("utf-8"), str(expires).encode("ascii"), hashlib.sha256).digest())


def issue_session(secret: str, *, now: int | None = None) -> str:
    timestamp = int(time.time() if now is None else now)
    expires = timestamp + _SESSION_SECONDS
    return f"{expires}.{_signature(secret, expires)}"


def verify_session(cookie_header: str | None, secret: str | None, *, now: int | None = None) -> bool:
    if not secret:
        return True
    if not cookie_header:
        return False
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header)
        raw = cookie[_COOKIE].value
        expires_text, signature = raw.split(".", 1)
        expires = int(expires_text)
    except (KeyError, ValueError, TypeError):
        return False
    timestamp = int(time.time() if now is None else now)
    if expires < timestamp:
        return False
    return hmac.compare_digest(signature, _signature(secret, expires))


def verify_login_body(body: bytes, secret: str | None) -> bool:
    if not secret:
        return True
    try:
        values = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        supplied = values.get("password", [""])[0]
    except (UnicodeDecodeError, ValueError):
        return False
    return hmac.compare_digest(supplied, secret)


def session_cookie(secret: str, *, secure: bool = True) -> str:
    parts = [
        f"{_COOKIE}={issue_session(secret)}",
        "Path=/",
        f"Max-Age={_SESSION_SECONDS}",
        "HttpOnly",
        "SameSite=Strict",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clear_cookie(*, secure: bool = True) -> str:
    parts = [f"{_COOKIE}=", "Path=/", "Max-Age=0", "HttpOnly", "SameSite=Strict"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def login_html(*, invalid: bool = False) -> str:
    message = '<p class="error">Senha inválida.</p>' if invalid else ""
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de Conflitos — acesso privado</title>
<style>body{{font-family:system-ui,sans-serif;background:#101214;color:#e9ecef;display:grid;place-items:center;min-height:100vh;margin:0}}main{{width:min(360px,88vw);background:#181c20;border:1px solid #2b3137;border-radius:10px;padding:24px}}input,button{{box-sizing:border-box;width:100%;padding:11px;margin-top:10px;border-radius:6px;border:1px solid #3a4046;background:#24282c;color:#fff}}button{{cursor:pointer}}.meta{{color:#adb5bd;font-size:13px}}.error{{color:#ff8787}}</style></head>
<body><main><h2>Monitor de Conflitos</h2><p class="meta">Acesso privado</p>{message}<form method="post" action="/login"><input name="password" type="password" autocomplete="current-password" placeholder="Senha" autofocus required><button type="submit">Entrar</button></form></main></body></html>'''


def safe_return_path(value: str | None) -> str:
    text = html.unescape(str(value or "")).strip()
    if not text.startswith("/") or text.startswith("//"):
        return "/dashboard"
    return text

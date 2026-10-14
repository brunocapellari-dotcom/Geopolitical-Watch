from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from geowatch.private_api import PrivateHandler, _private_dashboard_html, _private_operational_page_html
from geowatch.web_auth import clear_cookie, issue_session, login_html, session_cookie, verify_login_body, verify_session


class PrivateAuthTests(unittest.TestCase):
    def test_signed_session_round_trip_and_expiry(self) -> None:
        secret = "correct-horse-battery-staple"
        token = issue_session(secret, now=1000)
        header = f"geowatch_session={token}"
        self.assertTrue(verify_session(header, secret, now=1001))
        self.assertFalse(verify_session(header, secret + "x", now=1001))
        self.assertFalse(verify_session(header, secret, now=1000 + 12 * 60 * 60 + 1))

    def test_login_uses_constant_secret_contract(self) -> None:
        secret = "private-secret"
        self.assertTrue(verify_login_body(b"password=private-secret", secret))
        self.assertFalse(verify_login_body(b"password=wrong", secret))

    def test_cookie_security_attributes(self) -> None:
        cookie = session_cookie("secret", secure=True)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertIn("Secure", cookie)
        cleared = clear_cookie(secure=True)
        self.assertIn("Max-Age=0", cleared)

    def test_login_page_does_not_embed_secret(self) -> None:
        html = login_html(invalid=True)
        self.assertIn("Acesso privado", html)
        self.assertIn("Senha inválida", html)
        self.assertNotIn("private-secret", html)

    def test_authenticated_dashboard_hides_bearer_field(self) -> None:
        html = _private_dashboard_html()
        self.assertIn('id="token" type="hidden"', html)
        self.assertNotIn('type="password" placeholder="API bearer token"', html)
        self.assertIn('href="/logout"', html)

    def test_authenticated_operational_page_hides_bearer_field(self) -> None:
        html = _private_operational_page_html("overview")
        self.assertIn('id="token" type="hidden"', html)
        self.assertNotIn('type="password" placeholder="API bearer token"', html)
        self.assertIn('href="/logout"', html)

    def test_operational_page_without_session_returns_login(self) -> None:
        fake = Mock()
        fake.path = "/overview"
        fake.headers = {}
        with patch("geowatch.private_api.API_TOKEN", "s" * 40), \
             patch("geowatch.private_api.verify_session", return_value=False):
            PrivateHandler.do_GET(fake)
        self.assertTrue(fake._send_text.called)
        body = fake._send_text.call_args.args[1]
        self.assertIn("Acesso privado", body)


if __name__ == "__main__":
    unittest.main()

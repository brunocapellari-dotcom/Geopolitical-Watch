from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()

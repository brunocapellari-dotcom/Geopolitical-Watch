from __future__ import annotations

import unittest

from geowatch.http import validate_web_url


class HttpSecurityTests(unittest.TestCase):
    def test_rejects_localhost_and_private_ip_literals(self) -> None:
        for url in (
            "http://localhost/admin",
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_web_url(url)

    def test_accepts_public_http_and_https(self) -> None:
        self.assertEqual("https://example.org/path", validate_web_url("https://example.org/path"))
        self.assertEqual("http://8.8.8.8/", validate_web_url("http://8.8.8.8/"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from defusedxml.common import DefusedXmlException

from geowatch.delivery import dispatch_pending
from geowatch.http import validate_web_url
from geowatch.sanctions_feed import parse_un_consolidated_xml


class _EmptyStore:
    def pending_alerts(self, *, limit: int = 100):
        return []


class SecurityHardeningTests(unittest.TestCase):
    def test_outbound_url_rejects_file_custom_and_embedded_credentials(self) -> None:
        for value in (
            "file:///etc/passwd",
            "ftp://example.com/data",
            "gopher://example.com/",
            "https://user:pass@example.com/path",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_web_url(value)
        self.assertEqual(validate_web_url("https://example.com/path"), "https://example.com/path")

    def test_production_webhook_requires_https(self) -> None:
        env = {"REPLIT_DEPLOYMENT": "1"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError):
                dispatch_pending(_EmptyStore(), webhook_url="http://example.com/hook")
            result = dispatch_pending(_EmptyStore(), webhook_url="https://example.com/hook")
        self.assertEqual(result["pending"], 0)
        self.assertEqual(result["delivered"], 0)

    def test_un_sanctions_xml_rejects_entity_expansion(self) -> None:
        payload = b'''<?xml version="1.0"?>
        <!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
        <root><ENTITY><NAME>&xxe;</NAME></ENTITY></root>'''
        with self.assertRaises(DefusedXmlException):
            parse_un_consolidated_xml(payload, collected_at="2026-09-15T00:00:00Z")


if __name__ == "__main__":
    unittest.main()

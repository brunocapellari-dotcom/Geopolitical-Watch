from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geowatch.entities import EntityResolver
from geowatch.geolocation import from_source_coordinates, resolve_known_location
from geowatch.models import Entity
from geowatch.research_adapters import BrowserAgentRequired, browsertrix_command, request_browser_agent
from geowatch.text_enrichment import attach_translation, detect_language, envelope_text


class V017ResearchEnrichmentTests(unittest.TestCase):
    def test_language_preserves_original_and_translation(self) -> None:
        language, method = detect_language("غزة")
        self.assertEqual("ar", language)
        self.assertIn(method, {"lingua", "unicode-script"})
        original = envelope_text("texto original", declared_language="pt")
        translated = attach_translation(
            original,
            translated_text="original text",
            translated_language="en",
            method="test-translator",
        )
        self.assertEqual("texto original", translated.original_text)
        self.assertEqual("original text", translated.translated_text)

    def test_geolocation_never_guesses_unknown_coordinates(self) -> None:
        resolver = EntityResolver([
            Entity(
                entity_id="ent-port",
                entity_type="port",
                canonical_name="Known Port",
                latitude=1.0,
                longitude=2.0,
            )
        ])
        known = resolve_known_location("Known Port", resolver=resolver)
        self.assertEqual(1.0, known.confidence)
        unknown = resolve_known_location("Unknown Place", resolver=resolver)
        self.assertEqual(0.0, unknown.confidence)
        self.assertIsNone(unknown.latitude)

    def test_source_coordinates_validate_range(self) -> None:
        row = from_source_coordinates(name="site", latitude=10.0, longitude=20.0)
        self.assertEqual("source-provided", row.method)
        with self.assertRaises(ValueError):
            from_source_coordinates(name="bad", latitude=100.0, longitude=20.0)

    @patch("geowatch.research_adapters.validate_web_url", side_effect=lambda url: url)
    def test_browsertrix_command_is_argument_vector_and_page_scoped(self, _validate) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            command = browsertrix_command(
                "https://example.com/report",
                output_dir=tmp,
                collection="evidence-1",
            )
        self.assertEqual("docker", command[0])
        self.assertIn("--generateWACZ", command)
        self.assertIn("--scopeType", command)
        self.assertNotIn("--profile", command)

    @patch("geowatch.research_adapters.validate_web_url", side_effect=lambda url: url)
    def test_browser_agent_is_explicit_isolated_handoff(self, _validate) -> None:
        with self.assertRaises(BrowserAgentRequired):
            request_browser_agent("https://example.com", reason="interactive workflow")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from geowatch.dashboard import dashboard_html
from geowatch.private_api_final import PrivateHandler
from geowatch.runtime_guard import production_requirements
from geowatch.runtime_readiness import build_runtime_readiness


class FinalWebRuntimeTests(unittest.TestCase):
    def test_dashboard_uses_maplibre_v6_esm_not_legacy_bundle_or_leaflet(self) -> None:
        html = dashboard_html()
        self.assertIn("maplibre-gl@6.9.1", html)
        self.assertIn('<script type="module">', html)
        self.assertIn("dist/maplibre-gl.mjs", html)
        self.assertNotIn('src="https://unpkg.com/maplibre-gl@6.9.1/dist/maplibre-gl.js"', html)
        self.assertIn("new maplibregl.Map", html)
        self.assertNotIn("leaflet@", html.casefold())
        self.assertNotIn("L.map(", html)
        self.assertIn("cluster:true", html)
        self.assertIn("/v2/live/aircraft", html)
        self.assertIn("/v2/live/vessels", html)
        self.assertIn("/v2/verification/episode", html)
        self.assertIn("/v2/context/physical", html)
        self.assertIn("/v2/context/network", html)
        self.assertIn("geowatch-map-layers-v1", html)
        self.assertIn("window.__geowatchMapReady", html)

    def test_custom_map_style_is_serialized_not_interpolated_as_code(self) -> None:
        malicious = 'https://maps.example/style.json";alert(1);//'
        with patch.dict(os.environ, {"GEOWATCH_MAP_STYLE_URL": malicious}, clear=True):
            html = dashboard_html()
        self.assertIn('const MAP_STYLE="https://maps.example/style.json\\";alert(1);//";', html)
        self.assertNotIn('const MAP_STYLE=https://maps.example', html)

    def test_external_scheduler_is_valid_exclusive_production_collection_path(self) -> None:
        env = {
            "GEOWATCH_API_TOKEN": "s" * 40,
            "GEOWATCH_DB_URL": "postgresql://user:pass@host/db",
            "GEOWATCH_RAW_BACKEND": "postgres",
            "GEOWATCH_EXTERNAL_SCHEDULER": "1",
            "GEOWATCH_COOKIE_SECURE": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            checks = production_requirements()
            readiness = build_runtime_readiness()
        self.assertTrue(checks["collection_path_configured"])
        self.assertTrue(checks["duplicate_collectors_disabled"])
        self.assertTrue(readiness["private_web_ready"])
        self.assertEqual(readiness["collection_mode"], "external_cloud_scheduler")

    def test_multiple_collection_modes_fail_exclusivity(self) -> None:
        env = {
            "GEOWATCH_API_TOKEN": "s" * 40,
            "GEOWATCH_DB_URL": "postgresql://user:pass@host/db",
            "GEOWATCH_RAW_BACKEND": "postgres",
            "GEOWATCH_EXTERNAL_SCHEDULER": "1",
            "GEOWATCH_SOURCE_SCHEDULER": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            checks = production_requirements()
        self.assertFalse(checks["collection_path_configured"])
        self.assertFalse(checks["duplicate_collectors_disabled"])

    def test_final_handler_is_the_security_header_owner(self) -> None:
        self.assertTrue(issubclass(PrivateHandler, object))
        self.assertIn("end_headers", PrivateHandler.__dict__)


if __name__ == "__main__":
    unittest.main()

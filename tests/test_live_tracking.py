from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from geowatch.dashboard import dashboard_html
from geowatch.http import HttpResponse
from geowatch.live_aircraft import aircraft_route, aircraft_snapshot, clear_live_aircraft_cache


class LiveTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_live_aircraft_cache()

    def test_aircraft_snapshot_validates_normalizes_and_caches(self) -> None:
        payload = {
            "ac": [
                {
                    "hex": "e49001",
                    "flight": "GLO1234 ",
                    "r": "PRABC",
                    "t": "B738",
                    "lat": -15.6,
                    "lon": -56.1,
                    "alt_baro": 35000,
                    "gs": 450.5,
                    "track": 92.0,
                    "seen": 1.2,
                }
            ]
        }
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            return HttpResponse(json.dumps(payload).encode(), url, "application/json")

        with patch("geowatch.live_aircraft.get", fake_get):
            first = aircraft_snapshot(-15.6, -56.1, 120)
            second = aircraft_snapshot(-15.6, -56.1, 120)

        self.assertEqual(len(calls), 1)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["aircraft"][0]["registration"], "PRABC")
        self.assertEqual(first["ac"][0]["alt_baro"], 35000)
        self.assertIn("/dist/120", calls[0])

    def test_aircraft_snapshot_rejects_unbounded_input(self) -> None:
        with self.assertRaises(ValueError):
            aircraft_snapshot(91, 0, 100)
        with self.assertRaises(ValueError):
            aircraft_snapshot(0, 0, 251)

    def test_route_is_context_not_confirmed_flight_plan(self) -> None:
        payload = {
            "airport_codes": "SBGR-KMIA",
            "plausible": True,
            "_airports": [
                {"icao": "SBGR", "iata": "GRU", "name": "Guarulhos", "lat": -23.43, "lon": -46.47},
                {"icao": "KMIA", "iata": "MIA", "name": "Miami", "lat": 25.79, "lon": -80.29},
            ],
        }

        def fake_get(url, **kwargs):
            return HttpResponse(json.dumps(payload).encode(), url, "application/json")

        with patch("geowatch.live_aircraft.get", fake_get):
            route = aircraft_route("GLO1234", -10, -50)
        self.assertTrue(route["plausible"])
        self.assertEqual(route["_airports"][0]["icao"], "SBGR")
        self.assertIn("not a confirmed filed flight plan", route["route_semantics"])

    def test_route_rejects_unsafe_callsign(self) -> None:
        with self.assertRaises(ValueError):
            aircraft_route("../../etc/passwd", 0, 0)

    def test_dashboard_uses_private_backend_for_aircraft(self) -> None:
        html = dashboard_html()
        self.assertIn("/v2/live/aircraft", html)
        self.assertIn("/v2/live/aircraft/route", html)
        self.assertNotIn("https://api.adsb.lol", html)
        self.assertIn("API bearer token", html)


if __name__ == "__main__":
    unittest.main()

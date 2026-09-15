from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from geowatch.dashboard import dashboard_html
from geowatch.live_vessels import _consume, provider_status, reset_for_tests, vessel_snapshot
from geowatch.map_layers import layer_index


class LiveVesselTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_for_tests()

    def tearDown(self) -> None:
        reset_for_tests()

    def test_unconfigured_provider_is_inert(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            status = provider_status()
            snapshot = vessel_snapshot()
        self.assertFalse(status["configured"])
        self.assertFalse(snapshot["configured"])
        self.assertEqual(snapshot["vessels"], [])
        self.assertGreater(status["regions"], 0)

    def test_position_report_is_normalized(self) -> None:
        event = {
            "MessageType": "PositionReport",
            "MetaData": {
                "MMSI": 368207620,
                "ShipName": "EXAMPLE VESSEL",
                "Latitude": 25.7617,
                "Longitude": -80.1918,
            },
            "Message": {
                "PositionReport": {
                    "Sog": 12.4,
                    "Cog": 86.7,
                    "TrueHeading": 87,
                    "NavigationalStatus": 0,
                }
            },
        }
        _consume(json.dumps(event).encode(), max_vessels=100)
        with patch.dict(os.environ, {}, clear=True):
            snapshot = vessel_snapshot()
        self.assertEqual(snapshot["count"], 1)
        vessel = snapshot["vessels"][0]
        self.assertEqual(vessel["mmsi"], "368207620")
        self.assertEqual(vessel["ship_name"], "EXAMPLE VESSEL")
        self.assertEqual(vessel["speed_over_ground_kt"], 12.4)
        self.assertIn("not verified voyage intent", vessel["ais_semantics"])

    def test_static_update_preserves_position_and_adds_voyage_context(self) -> None:
        position = {
            "MessageType": "PositionReport",
            "MetaData": {"MMSI": 123456789, "ShipName": "SHIP", "Latitude": 1.2, "Longitude": 3.4},
            "Message": {"PositionReport": {"Sog": 7.0, "Cog": 90.0, "TrueHeading": 90}},
        }
        static = {
            "MessageType": "ShipStaticData",
            "MetaData": {"MMSI": 123456789, "ShipName": "SHIP"},
            "Message": {"ShipStaticData": {
                "Name": "SHIP",
                "ImoNumber": 9876543,
                "CallSign": "PXAB",
                "Type": 70,
                "Destination": "SANTOS",
                "Eta": {"Month": 9, "Day": 20, "Hour": 14, "Minute": 30},
                "MaximumStaticDraught": 11.2,
            }},
        }
        _consume(json.dumps(position), max_vessels=100)
        _consume(json.dumps(static), max_vessels=100)
        with patch.dict(os.environ, {}, clear=True):
            vessel = vessel_snapshot()["vessels"][0]
        self.assertEqual(vessel["lat"], 1.2)
        self.assertEqual(vessel["lon"], 3.4)
        self.assertEqual(vessel["reported_destination"], "SANTOS")
        self.assertEqual(vessel["imo_number"], 9876543)
        self.assertEqual(vessel["call_sign"], "PXAB")
        self.assertEqual(vessel["maximum_static_draught_m"], 11.2)
        self.assertIn("09-20 14:30 UTC", vessel["reported_eta"])
        self.assertIn("vessel-declared", vessel["ais_semantics"])

    def test_snapshot_can_be_bounded_to_map_view(self) -> None:
        for mmsi, lat, lon, name in (
            (111111111, -24.0, -46.0, "SANTOS SHIP"),
            (222222222, 25.0, 56.0, "HORMUZ SHIP"),
        ):
            event = {
                "MessageType": "PositionReport",
                "MetaData": {"MMSI": mmsi, "ShipName": name, "Latitude": lat, "Longitude": lon},
                "Message": {"PositionReport": {"Sog": 10.0, "Cog": 45.0, "TrueHeading": 45}},
            }
            _consume(json.dumps(event), max_vessels=100)
        with patch.dict(os.environ, {}, clear=True):
            snapshot = vessel_snapshot(south=-28, west=-51, north=-22, east=-43, limit=50)
        self.assertEqual(snapshot["active_total"], 2)
        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(snapshot["vessels"][0]["ship_name"], "SANTOS SHIP")
        self.assertFalse(snapshot["truncated"])

    def test_snapshot_rejects_incomplete_or_unbounded_bbox(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                vessel_snapshot(south=-10)
            with self.assertRaises(ValueError):
                vessel_snapshot(south=-91, west=0, north=10, east=10)
            with self.assertRaises(ValueError):
                vessel_snapshot(limit=5001)

    def test_dashboard_keeps_ais_opt_in(self) -> None:
        html = dashboard_html()
        vessels = layer_index()["vessels"]
        self.assertEqual(vessels["label"], "Navios AIS")
        self.assertEqual(vessels["semantic_class"], "OBSERVADO")
        self.assertEqual(vessels["source"], "AISStream")
        self.assertFalse(vessels["default_visible"])
        self.assertIn('data-layer="vessels">Navios AIS', html)
        self.assertNotIn('data-layer="vessels" checked', html)
        self.assertIn("/v2/live/vessels", html)
        self.assertIn("if(!visible('vessels'))return", html)
        self.assertIn("if(visible('vessels'))loadVessels()", html)
        self.assertIn("60000", html)
        self.assertIn("maplibre", html.casefold())


if __name__ == "__main__":
    unittest.main()

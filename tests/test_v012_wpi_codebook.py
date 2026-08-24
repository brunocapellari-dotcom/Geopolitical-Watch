from __future__ import annotations

import unittest

from geowatch.wpi import candidate_score, to_infrastructure_node


class WPICodebookAlignmentTests(unittest.TestCase):
    def test_official_downloaded_field_names_are_supported(self):
        row = {
            "wpinumber": "12345",
            "main_port_": "Example Port",
            "alternate_": "Example Harbor",
            "unlocode": "XXEXP",
            "countryCode": "XX",
            "dodwaterbo": "Example Sea",
            "navarea": "III",
            "Latitude": "10.5",
            "Longitude": "20.25",
            "harbor_siz": "Large",
            "harbor_typ": "Coastal (Natural)",
            "harbor_use": "Cargo",
            "fac_contai": "Yes",
            "fac_oilter": "Yes",
            "fac_lngter": "No",
            "fac_solidb": "Yes",
            "fac_liquid": "Yes",
            "fac_roro": "No",
            "com_rail": "Yes",
            "vts": "Yes",
            "tss": "Yes",
            "channel_de": "14.2",
            "cargo_pier": "13.4",
            "oil_termin": "15.0",
            "lng_termin": "0",
            "maxvessell": "350",
            "maxvesselb": "52",
            "maxvesseld": "14.5",
        }
        node = to_infrastructure_node(row)
        self.assertIsNotNone(node)
        assert node is not None
        self.assertEqual("WPI_12345", node["node_id"])
        self.assertEqual("Example Port", node["name"])
        self.assertEqual("Example Harbor", node["alternate_name"])
        self.assertEqual("XXEXP", node["un_locode"])
        self.assertEqual("Example Sea", node["water_body"])
        self.assertIn("Container", node["facilities"])
        self.assertIn("Oil Terminal", node["facilities"])
        self.assertIn("Solid Bulk", node["facilities"])
        self.assertTrue(node["rail_communications"])
        self.assertTrue(node["vessel_traffic_service"])
        self.assertEqual(14.2, node["depth_m"]["channel"])
        self.assertEqual(350.0, node["max_vessel_m"]["length"])
        self.assertGreater(candidate_score(row), 15)
        self.assertTrue(node["structural_context_not_live_status"])


if __name__ == "__main__":
    unittest.main()

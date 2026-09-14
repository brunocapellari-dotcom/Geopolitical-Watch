from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from geowatch.runtime_wpi import clear_runtime_wpi_cache, load_runtime_wpi


class RuntimeWPITests(unittest.TestCase):
    def setUp(self) -> None:
        clear_runtime_wpi_cache()

    def tearDown(self) -> None:
        clear_runtime_wpi_cache()

    def test_runtime_wpi_is_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            nodes, status = load_runtime_wpi()
        self.assertEqual(nodes, [])
        self.assertEqual(status["status"], "disabled")

    def test_runtime_wpi_loads_official_rows_and_caches(self) -> None:
        rows = [
            {
                "WPI Number": "1234",
                "Main Port Name": "Example Port",
                "Country Code": "BR",
                "Latitude": "-23.9",
                "Longitude": "-46.3",
                "Harbor Size": "Large",
                "Facilities - Container": "Yes",
            }
        ]
        calls = []

        def fake_download():
            calls.append(1)
            return rows, "https://example.invalid/wpi.csv"

        with patch.dict(os.environ, {"GEOWATCH_WPI_RUNTIME": "1"}, clear=True), patch("geowatch.runtime_wpi.download", fake_download):
            first_nodes, first_status = load_runtime_wpi(limit=300)
            second_nodes, second_status = load_runtime_wpi(limit=300)

        self.assertEqual(len(calls), 1)
        self.assertEqual(first_status["status"], "ok")
        self.assertFalse(first_status["cache_hit"])
        self.assertTrue(second_status["cache_hit"])
        self.assertEqual(first_nodes[0]["name"], "Example Port")
        self.assertEqual(first_nodes[0]["latitude"], -23.9)
        self.assertEqual(second_nodes[0]["longitude"], -46.3)

    def test_runtime_wpi_fails_soft(self) -> None:
        with patch.dict(os.environ, {"GEOWATCH_WPI_RUNTIME": "1"}, clear=True), patch("geowatch.runtime_wpi.download", side_effect=OSError("network down")):
            nodes, status = load_runtime_wpi()
        self.assertEqual(nodes, [])
        self.assertEqual(status["status"], "error")
        self.assertIn("OSError", status["error"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from geowatch.dashboard import dashboard_html


class V017DashboardContractTests(unittest.TestCase):
    def test_dashboard_exposes_operational_event_filters(self) -> None:
        body = dashboard_html()
        for identifier in (
            'id="regionFilter"',
            'id="actorFilter"',
            'id="typeFilter"',
            'id="confidenceFilter"',
            'id="hoursFilter"',
            'id="events"',
        ):
            self.assertIn(identifier, body)
        self.assertIn("/v2/events?", body)
        self.assertIn("renderEvents", body)

    def test_deck_density_is_optional_and_non_blocking(self) -> None:
        body = dashboard_html()
        self.assertIn("MapLibreOverlay", body)
        self.assertIn("HeatmapLayer", body)
        self.assertIn("try{const maplibreDeck=await import(", body)
        self.assertIn("window.__geowatchMapReady=true", body)
        self.assertIn("window.__geowatchDeckReady=false", body)


if __name__ == "__main__":
    unittest.main()

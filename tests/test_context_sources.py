from __future__ import annotations

import json
import unittest

from geowatch.sources import ioda, ripestat, usgs


class ContextSourceTests(unittest.TestCase):
    def test_usgs_geojson_is_observed_physical_context(self) -> None:
        payload = json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "id": "us-test-1",
                "properties": {"mag": 5.2, "place": "10 km W of Example", "time": 1789440000000, "url": "https://earthquake.usgs.gov/example"},
                "geometry": {"type": "Point", "coordinates": [51.0, 35.0, 12.0]},
            }],
        }).encode()
        rows = usgs.parse(payload, collected_at="2026-09-15T00:00:00+00:00", raw_ref="raw://x")
        self.assertEqual(len(rows), 1)
        event = rows[0]
        self.assertEqual(event.event_type, "earthquake")
        self.assertEqual(event.verification_level, "sensor_signal")
        self.assertEqual(event.evidence_class, "observed")
        self.assertEqual(event.publisher, "USGS Earthquake Hazards Program")
        self.assertEqual((event.latitude, event.longitude), (35.0, 51.0))

    def test_ripestat_only_emits_material_visibility_degradation(self) -> None:
        good = json.dumps({"data": {"resource": "AS64500", "visibility": {"v4": {"ris_peers_seeing": 90, "total_ris_peers": 100}}}}).encode()
        bad = json.dumps({"data": {"resource": "AS64500", "visibility": {"v4": {"ris_peers_seeing": 40, "total_ris_peers": 100}}}}).encode()
        self.assertEqual(ripestat.parse(good, collected_at="2026-09-15T00:00:00+00:00"), [])
        rows = ripestat.parse(bad, collected_at="2026-09-15T00:00:00+00:00")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].event_type, "bgp_visibility_degradation")
        self.assertEqual(rows[0].evidence_class, "observed")

    def test_ioda_envelope_variants_are_parsed_as_sensor_context(self) -> None:
        payload = json.dumps({"data": {"alerts": [{
            "id": "alert-1", "entityName": "Example Network", "countryCode": "ZZ",
            "start": 1789440000, "score": 0.91,
        }]}}).encode()
        rows = ioda.parse(payload, collected_at="2026-09-15T00:00:00+00:00")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].event_type, "internet_connectivity_outage_signal")
        self.assertEqual(rows[0].country, "ZZ")
        self.assertEqual(rows[0].verification_level, "sensor_signal")


if __name__ == "__main__":
    unittest.main()

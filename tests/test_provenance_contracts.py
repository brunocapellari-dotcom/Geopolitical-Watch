from __future__ import annotations

import json
import unittest

from geowatch.entities import EntityResolver
from geowatch.models import Entity
from geowatch.sources import acled, gdacs, ucdp


class ProvenanceContractsTests(unittest.TestCase):
    def test_gdacs_source_coordinates_are_reported_not_inferred(self) -> None:
        payload = json.dumps({
            "features": [{
                "geometry": {"type": "Point", "coordinates": [32.35, 30.45]},
                "properties": {
                    "eventid": "GDACS-1",
                    "eventtype": "FL",
                    "name": "Flood near corridor",
                    "country": "Egypt",
                    "fromdate": "2026-10-07T08:00:00Z",
                },
            }]
        }).encode()
        event = gdacs.parse(payload, collected_at="2026-10-07T09:00:00+00:00")[0]
        self.assertEqual("reported", event.location_source)
        self.assertEqual("source_geometry", event.geolocation_method)
        self.assertEqual(0.95, event.geolocation_confidence)
        self.assertEqual("Flood near corridor", event.location)

    def test_acled_keeps_reported_location_and_coordinate_provenance(self) -> None:
        payload = json.dumps({"data": [{
            "event_id_cnty": "BR-1",
            "event_date": "2026-10-07",
            "event_type": "Battles",
            "sub_event_type": "Armed clash",
            "country": "Example",
            "admin1": "Region",
            "location": "Town",
            "latitude": "10.1",
            "longitude": "20.2",
        }]}).encode()
        event = acled.parse(payload, collected_at="2026-10-07T09:00:00+00:00")[0]
        self.assertEqual("Town", event.location)
        self.assertEqual("reported", event.location_source)
        self.assertEqual("source_coordinates", event.geolocation_method)
        self.assertEqual(0.95, event.geolocation_confidence)

    def test_ucdp_keeps_where_description_as_reported_location(self) -> None:
        payload = json.dumps({"Result": [{
            "id": 1,
            "date_start": "2026-10-07",
            "country": "Example",
            "where_description": "District X",
            "latitude": "11.1",
            "longitude": "22.2",
            "type_of_violence": 1,
        }]}).encode()
        event = ucdp.parse(payload, collected_at="2026-10-07T09:00:00+00:00")[0]
        self.assertEqual("District X", event.location)
        self.assertEqual("reported", event.location_source)
        self.assertEqual("source_coordinates", event.geolocation_method)

    def test_entity_resolution_preserves_raw_name_and_confidence(self) -> None:
        seeded = Entity(
            entity_id="ent_kyiv",
            entity_type="city",
            canonical_name="Kyiv",
            aliases=("Kiev",),
            country="Ukraine",
        )
        resolver = EntityResolver([seeded])
        resolved = resolver.resolve_name("Kiev", entity_type="city", country="Ukraine")
        self.assertEqual("ent_kyiv", resolved.entity_id)
        self.assertIn("Kiev", resolved.raw_names)
        self.assertEqual("kiev", resolved.normalized_name)
        self.assertEqual(0.95, resolved.resolution_confidence)

        unknown = resolver.resolve_name("Uncatalogued Place", entity_type="city", country="Example")
        self.assertEqual(("Uncatalogued Place",), unknown.raw_names)
        self.assertEqual("uncatalogued place", unknown.normalized_name)
        self.assertEqual(0.55, unknown.resolution_confidence)


if __name__ == "__main__":
    unittest.main()

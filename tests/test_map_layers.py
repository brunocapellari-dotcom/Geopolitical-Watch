from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from geowatch.map_layers import load_map_layers


class MapLayerCatalogTests(unittest.TestCase):
    def test_production_catalog_has_all_governed_layers(self) -> None:
        catalog = load_map_layers()
        rows = {row["id"]: row for row in catalog["layers"]}
        self.assertEqual(
            set(rows),
            {"conflicts", "infrastructure", "physical", "network", "aircraft", "vessels"},
        )
        self.assertEqual(rows["conflicts"]["semantic_class"], "INFERIDO")
        self.assertEqual(rows["aircraft"]["semantic_class"], "OBSERVADO")
        self.assertEqual(rows["vessels"]["semantic_class"], "OBSERVADO")
        self.assertEqual(rows["infrastructure"]["evidentiary_role"], "context")
        for row in rows.values():
            self.assertGreaterEqual(row["freshness_seconds"], row["refresh_seconds"])
            self.assertTrue(row["source"])
            self.assertTrue(row["note"])

    def test_catalog_rejects_duplicate_or_unknown_semantics(self) -> None:
        payload = {
            "schema_version": "geowatch-map-layers-v1",
            "layers": [
                {
                    "id": layer_id,
                    "label": layer_id,
                    "source": "test",
                    "semantic_class": "OBSERVADO",
                    "evidentiary_role": "context",
                    "default_visible": False,
                    "refresh_seconds": 60,
                    "freshness_seconds": 120,
                    "note": "test",
                }
                for layer_id in ("conflicts", "infrastructure", "physical", "network", "aircraft", "vessels")
            ],
        }
        payload["layers"][0]["semantic_class"] = "UNVERIFIED"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layers.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_map_layers(path)


if __name__ == "__main__":
    unittest.main()

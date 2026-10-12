from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path


class ToolingRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(Path("config/tooling_registry.json").read_text(encoding="utf-8"))
        self.tools = self.payload["tools"]

    def test_every_tool_has_a_governed_decision(self) -> None:
        self.assertEqual(self.payload["schema_version"], "geowatch-tooling-registry-v2")
        self.assertTrue(self.payload["governance"]["one_primary_per_capability"])
        self.assertTrue(self.payload["governance"]["unused_dependencies_forbidden"])
        for row in self.tools:
            with self.subTest(tool=row.get("name")):
                for key in ("capability", "name", "status", "integration_mode", "license", "decision", "rationale"):
                    self.assertTrue(str(row.get(key) or "").strip(), key)

    def test_only_one_primary_exists_per_capability(self) -> None:
        counts = Counter(row["capability"] for row in self.tools if row["status"] == "primary")
        self.assertTrue(counts)
        self.assertTrue(all(count == 1 for count in counts.values()))

    def test_reference_tools_are_not_runtime_dependencies(self) -> None:
        disallowed = {"runtime_library", "test_dependency", "ci_action", "server_side_websocket", "managed_database"}
        for row in self.tools:
            if row["status"] in {"reference_only", "conditional_reference"}:
                with self.subTest(tool=row["name"]):
                    self.assertNotIn(row["integration_mode"], disallowed)

    def test_worldmonitor_license_boundary_is_explicit(self) -> None:
        row = next(item for item in self.tools if item["name"] == "koala73/worldmonitor")
        self.assertEqual(row["license"], "AGPL-3.0-only")
        self.assertEqual(row["decision"], "concepts_only_no_code_import")


if __name__ == "__main__":
    unittest.main()

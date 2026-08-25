from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geowatch.knowledge_sync import build_obsidian_bundle, validate_obsidian_bundle
from geowatch.sources.un_comtrade import attach_domains, normalize_trade_records
from geowatch.sources.unlocode import parse_unlocode_csv, port_rows


class V014SourcesKnowledgeTests(unittest.TestCase):
    def test_unlocode_parser_marks_port_identity(self):
        payload=b",BR,SSZ,Santos,Santos,SP,1,AI,,,,\n"
        rows=parse_unlocode_csv(payload)
        self.assertEqual(1,len(rows))
        self.assertEqual("BRSSZ",rows[0]["unlocode"])
        self.assertTrue(rows[0]["is_port"])
        self.assertEqual(1,len(port_rows(rows)))
        self.assertTrue(rows[0]["identity_reference_not_criticality_evidence"])

    def test_comtrade_normalization_maps_energy(self):
        payload={"data":[{"period":2025,"reporterDesc":"A","partnerDesc":"B","flowCode":"M","cmdCode":"27","cmdDesc":"Energy","primaryValue":123}]}
        rows=attach_domains(normalize_trade_records(payload,collected_at="2026-08-25T00:00:00Z"))
        self.assertEqual("energy",rows[0]["domain"])
        self.assertEqual("imports",rows[0]["flow"])

    def test_obsidian_bundle_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"src"; out=Path(tmp)/"out"; src.mkdir()
            for i in range(5):
                (src/f"n{i}.md").write_text("---\ntitle: X\n---\n# X\n",encoding="utf-8")
            manifest=build_obsidian_bundle(src,out)
            result=validate_obsidian_bundle(manifest)
            self.assertTrue(result["passed"])
            self.assertTrue((out/"manifest.json").exists())


if __name__=="__main__": unittest.main()

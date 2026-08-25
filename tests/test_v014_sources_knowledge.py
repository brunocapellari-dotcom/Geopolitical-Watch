from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geowatch.knowledge_drift import compare_knowledge_manifests
from geowatch.knowledge_sync import build_obsidian_bundle, validate_obsidian_bundle
from geowatch.sources.un_comtrade import attach_domains, normalize_trade_records, query_trade
from geowatch.sources.unlocode import parse_unlocode_csv, port_rows
from geowatch.http import HttpResponse


class V014SourcesKnowledgeTests(unittest.TestCase):
    def test_unlocode_parser_marks_port_identity(self):
        payload=b",BR,SSZ,Santos,Santos,SP,1,AI,,,,\n"
        rows=parse_unlocode_csv(payload)
        self.assertEqual(1,len(rows)); self.assertEqual("BRSSZ",rows[0]["unlocode"]); self.assertTrue(rows[0]["is_port"])
        self.assertEqual(1,len(port_rows(rows))); self.assertTrue(rows[0]["identity_reference_not_criticality_evidence"])

    def test_unlocode_headered_status_function_order(self):
        payload=("Change,Country,Location,Name,NameWoDiacritics,Subdivision,Status,Function,Date,IATA,Coordinates,Remarks\n"
                 ",BR,SSZ,Santos,Santos,SP,AI,1-------,2501,,,\n").encode()
        row=parse_unlocode_csv(payload)[0]
        self.assertEqual("AI",row["status"]); self.assertEqual("1-------",row["function"]); self.assertTrue(row["is_port"])

    def test_comtrade_normalization_maps_energy(self):
        payload={"data":[{"period":2025,"reporterDesc":"A","partnerDesc":"B","flowCode":"M","cmdCode":"27","cmdDesc":"Energy","primaryValue":123}]}
        rows=attach_domains(normalize_trade_records(payload,collected_at="2026-08-25T00:00:00Z"))
        self.assertEqual("energy",rows[0]["domain"]); self.assertEqual("imports",rows[0]["flow"])

    def test_comtrade_partner_none_omits_world_partner_filter(self):
        body=b'{"data":[]}'
        with patch("geowatch.sources.un_comtrade.get",return_value=HttpResponse(body,"https://comtrade.test","application/json")) as mocked:
            result=query_trade(reporter_code=156,partner_code=None,period="2025",cmd_code="27",flow_code="M")
        query=mocked.call_args.kwargs["query"]
        self.assertNotIn("partnerCode",query); self.assertEqual("public_preview",result["auth_mode"])

    def test_obsidian_bundle_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"src"; out=Path(tmp)/"out"; src.mkdir()
            for i in range(5): (src/f"n{i}.md").write_text("---\ntitle: X\n---\n# X\n",encoding="utf-8")
            manifest=build_obsidian_bundle(src,out); result=validate_obsidian_bundle(manifest)
            self.assertTrue(result["passed"]); self.assertTrue((out/"manifest.json").exists())

    def test_knowledge_drift_detects_missing_or_changed_notes(self):
        gh={"notes":[{"file":"a.md","sha256":"1"},{"file":"b.md","sha256":"2"}]}; dr={"notes":[{"file":"a.md","sha256":"9"}]}
        result=compare_knowledge_manifests(gh,dr)
        self.assertTrue(result["drift_detected"]); self.assertEqual(["b.md"],result["missing_in_drive"]); self.assertEqual("a.md",result["content_mismatch"][0]["file"])


if __name__=="__main__": unittest.main()

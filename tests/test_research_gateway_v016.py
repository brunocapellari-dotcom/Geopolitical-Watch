from __future__ import annotations

import unittest

from geowatch.research_gateway import ResearchRequest, plan_research


class ResearchGatewayTests(unittest.TestCase):
    def test_article_uses_low_cost_path_first(self) -> None:
        plan = plan_research(ResearchRequest(
            source_id="official_news",
            url="https://example.org/report",
            kind="article",
            terms_approved=True,
        ))
        self.assertEqual(("direct_http", "snapshot", "article_extract"), plan.stages)

    def test_document_routes_to_document_parser(self) -> None:
        plan = plan_research(ResearchRequest(
            source_id="official_pdf",
            url="https://example.org/report.pdf",
            kind="document",
            terms_approved=True,
        ))
        self.assertIn("document_parse", plan.stages)
        self.assertNotIn("article_extract", plan.stages)

    def test_hostile_browser_work_requires_isolation(self) -> None:
        request = ResearchRequest(
            source_id="public_osint",
            url="https://example.org/post",
            kind="article",
            terms_approved=True,
            requires_js=True,
            hostile_content=True,
            browser_isolated=False,
        )
        with self.assertRaises(ValueError):
            plan_research(request)

    def test_browser_agent_is_last_resort_before_optional_capture(self) -> None:
        plan = plan_research(ResearchRequest(
            source_id="interactive_source",
            url="https://example.org/app",
            terms_approved=True,
            requires_js=True,
            interactive_required=True,
            browser_isolated=True,
            high_fidelity_preservation=True,
        ))
        self.assertEqual("browser_agent", plan.stages[-2])
        self.assertEqual("high_fidelity_capture", plan.stages[-1])

    def test_rights_gate_is_mandatory(self) -> None:
        with self.assertRaises(ValueError):
            plan_research(ResearchRequest(
                source_id="unknown",
                url="https://example.org/",
                terms_approved=False,
            ))


if __name__ == "__main__":
    unittest.main()

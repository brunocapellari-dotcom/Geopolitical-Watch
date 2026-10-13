from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .http import validate_web_url

ResearchKind = Literal["article", "document", "dataset", "generic"]


@dataclass(frozen=True)
class ResearchRequest:
    source_id: str
    url: str
    kind: ResearchKind = "generic"
    terms_approved: bool = False
    multi_page: bool = False
    requires_js: bool = False
    selector_resilience: bool = False
    interactive_required: bool = False
    hostile_content: bool = False
    browser_isolated: bool = False
    high_fidelity_preservation: bool = False


@dataclass(frozen=True)
class ResearchPlan:
    source_id: str
    url: str
    stages: tuple[str, ...]
    browser_isolation_required: bool
    derived_processing_only: bool = True
    policy_version: str = "geowatch-research-gateway-v1"

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["stages"] = list(self.stages)
        return row


def load_policy(path: str | Path = "config/research_gateway.json") -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    governance = payload.get("governance") or {}
    if governance.get("external_content_is_untrusted") is not True:
        raise ValueError("research gateway must treat external content as untrusted")
    if governance.get("access_control_bypass_forbidden") is not True:
        raise ValueError("research gateway must forbid access-control bypass")
    if governance.get("stealth_or_anti_bot_bypass_forbidden") is not True:
        raise ValueError("research gateway must forbid stealth/anti-bot bypass")
    if governance.get("immutable_snapshot_before_derived_processing") is not True:
        raise ValueError("research gateway must snapshot before derived processing")
    return payload


def plan_research(request: ResearchRequest, *, policy_path: str | Path = "config/research_gateway.json") -> ResearchPlan:
    load_policy(policy_path)
    url = validate_web_url(request.url)
    if not request.source_id.strip():
        raise ValueError("source_id is required")
    if not request.terms_approved:
        raise ValueError("source rights/terms gate is not approved")

    browser_needed = request.requires_js or request.interactive_required
    isolation_required = bool(request.hostile_content and browser_needed)
    if isolation_required and not request.browser_isolated:
        raise ValueError("hostile interactive content requires an isolated browser")

    stages: list[str] = ["direct_http", "snapshot"]
    if request.kind == "document":
        stages.append("document_parse")
    elif request.kind == "article":
        stages.append("article_extract")

    if request.multi_page:
        stages.append("crawl")
    if request.selector_resilience:
        stages.append("resilient_dom")
    if request.requires_js:
        stages.append("browser_render")
    if request.interactive_required:
        stages.append("browser_agent")
    if request.high_fidelity_preservation:
        stages.append("high_fidelity_capture")

    if "browser_agent" in stages and stages[-1] != "browser_agent" and not request.high_fidelity_preservation:
        raise AssertionError("browser agent must be the last-resort processing stage")

    return ResearchPlan(
        source_id=request.source_id,
        url=url,
        stages=tuple(dict.fromkeys(stages)),
        browser_isolation_required=isolation_required,
    )

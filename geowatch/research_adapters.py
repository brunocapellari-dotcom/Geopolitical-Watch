from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .http import validate_web_url


@dataclass(frozen=True)
class ResearchArtifact:
    adapter: str
    url: str
    content: str
    content_kind: str
    success: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def extract_article_html(html: str, *, url: str) -> ResearchArtifact:
    safe_url = validate_web_url(url)
    try:
        import trafilatura  # type: ignore
    except ImportError as exc:
        raise RuntimeError("article extraction requires the research extra") from exc
    extracted = trafilatura.extract(
        html,
        url=safe_url,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    return ResearchArtifact(
        adapter="trafilatura",
        url=safe_url,
        content=extracted or "",
        content_kind="article_text",
        success=bool(extracted),
    )


async def crawl_with_crawl4ai(url: str) -> ResearchArtifact:
    """Bounded Crawl4AI fetch with no stealth/evasion configuration."""
    safe_url = validate_web_url(url)
    try:
        from crawl4ai import AsyncWebCrawler  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Crawl4AI requires the research extra") from exc
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=safe_url)
    success = bool(getattr(result, "success", False))
    content = getattr(result, "cleaned_html", None) or str(getattr(result, "markdown", "") or "")
    if not success:
        raise RuntimeError(str(getattr(result, "error_message", "Crawl4AI failed"))[:1000])
    return ResearchArtifact(
        adapter="crawl4ai",
        url=safe_url,
        content=str(content),
        content_kind="cleaned_html",
    )


def crawl_with_crawl4ai_sync(url: str) -> ResearchArtifact:
    return asyncio.run(crawl_with_crawl4ai(url))


def fetch_with_scrapling(url: str) -> ResearchArtifact:
    """Use Scrapling's normal Fetcher only; stealth/anti-bot modes are forbidden."""
    safe_url = validate_web_url(url)
    try:
        from scrapling.fetchers import Fetcher  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Scrapling requires the research extra") from exc
    page = Fetcher.get(safe_url)
    content = str(getattr(page, "html_content", "") or "")
    return ResearchArtifact(
        adapter="scrapling-fetcher",
        url=safe_url,
        content=content,
        content_kind="html",
        success=bool(content),
    )


def render_with_playwright(url: str) -> ResearchArtifact:
    """Render JavaScript when required, without stealth plugins or bypass logic."""
    safe_url = validate_web_url(url)
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Playwright requires the research extra") from exc
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(safe_url, wait_until="domcontentloaded", timeout=60_000)
            content = page.content()
        finally:
            browser.close()
    return ResearchArtifact(
        adapter="playwright",
        url=safe_url,
        content=content,
        content_kind="rendered_html",
        success=bool(content),
    )


def browsertrix_command(
    url: str,
    *,
    output_dir: str | Path,
    collection: str,
    image: str = "webrecorder/browsertrix-crawler:latest",
) -> list[str]:
    """Build a high-fidelity page-scoped WACZ capture command.

    The command deliberately omits profiles, stealth plugins and bypass features.
    """
    safe_url = validate_web_url(url)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", collection):
        raise ValueError("invalid Browsertrix collection name")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    return [
        "docker", "run", "--rm",
        "-v", f"{output}:/crawls",
        image,
        "crawl",
        "--url", safe_url,
        "--scopeType", "page",
        "--generateWACZ",
        "--text", "to-warc",
        "--screenshot", "view",
        "--collection", collection,
    ]


def capture_with_browsertrix(
    url: str,
    *,
    output_dir: str | Path,
    collection: str,
    timeout_seconds: int = 600,
    image: str = "webrecorder/browsertrix-crawler:latest",
) -> subprocess.CompletedProcess[str]:
    command = browsertrix_command(url, output_dir=output_dir, collection=collection, image=image)
    return subprocess.run(  # nosec B603 - fixed executable and validated argument vector
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=max(30, min(int(timeout_seconds), 3600)),
    )


class BrowserAgentRequired(RuntimeError):
    def __init__(self, *, url: str, reason: str) -> None:
        self.url = validate_web_url(url)
        self.reason = reason
        super().__init__(f"isolated browser agent required: {reason}")


def request_browser_agent(url: str, *, reason: str) -> None:
    """Explicit handoff marker; execution belongs to an isolated approved agent runtime."""
    raise BrowserAgentRequired(url=url, reason=reason)

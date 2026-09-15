from __future__ import annotations

import os
import sys
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def main() -> int:
    base = os.environ.get("GEOWATCH_E2E_URL", "http://127.0.0.1:8080/")
    token = os.environ.get("GEOWATCH_E2E_TOKEN", "")
    if not token:
        raise RuntimeError("GEOWATCH_E2E_TOKEN is required")

    page_errors: list[str] = []
    severe_console: list[str] = []
    network_failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on("requestfailed", lambda request: network_failures.append(f"{request.method} {request.url}: {request.failure}"))

        def console_handler(message) -> None:
            text = message.text
            if message.type == "error" and not any(
                allowed in text
                for allowed in (
                    "tile.openstreetmap.org",
                    "Failed to load resource",
                )
            ):
                severe_console.append(text)

        page.on("console", console_handler)
        try:
            page.goto(urljoin(base, "dashboard"), wait_until="domcontentloaded", timeout=30000)
            page.locator('input[name="password"]').fill(token)
            page.locator('button[type="submit"]').click()
            page.wait_for_url("**/dashboard", timeout=10000)
            page.wait_for_selector(".maplibregl-canvas", timeout=30000)
            page.wait_for_function("() => window.__geowatchMapReady === true", timeout=30000)
            page.wait_for_function(
                "() => document.getElementById('status') && document.getElementById('status').textContent !== 'carregando'",
                timeout=30000,
            )
        except PlaywrightTimeoutError as exc:
            snapshot = page.content()[:4000]
            diagnostics = [
                f"timeout: {exc}",
                "page_errors=" + repr(page_errors[:8]),
                "console_errors=" + repr(severe_console[:8]),
                "network_failures=" + repr(network_failures[:8]),
                "html_prefix=" + repr(snapshot),
            ]
            browser.close()
            raise AssertionError("browser bootstrap failed: " + " | ".join(diagnostics)) from exc

        html = page.content()
        if "maplibregl-canvas" not in html:
            raise AssertionError("MapLibre canvas did not render")
        if "leaflet-container" in html:
            raise AssertionError("legacy Leaflet renderer is still active")

        readiness = page.evaluate(
            """async () => {
                const response = await fetch('/v2/runtime/readiness');
                return {status: response.status, body: await response.json()};
            }"""
        )
        if readiness["status"] != 200:
            raise AssertionError(f"authenticated readiness endpoint returned {readiness['status']}")
        if "schema_version" not in readiness["body"]:
            raise AssertionError("readiness payload is missing schema_version")

        browser.close()

    worker_or_csp = [
        text
        for text in page_errors + severe_console
        if "content security policy" in text.casefold()
        or "worker" in text.casefold()
        or "maplibre" in text.casefold()
    ]
    if worker_or_csp:
        raise AssertionError("browser security/rendering errors: " + " | ".join(worker_or_csp[:5]))
    if page_errors:
        raise AssertionError("browser page errors: " + " | ".join(page_errors[:5]))
    if severe_console:
        raise AssertionError("browser console errors: " + " | ".join(severe_console[:5]))

    print("browser-smoke: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())

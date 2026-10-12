from __future__ import annotations

import threading
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from geowatch.api import Handler
from geowatch.dashboard import operational_page_html


class DashboardPagesTests(unittest.TestCase):
    def test_operational_page_renderer_marks_active_page(self) -> None:
        body = operational_page_html("sources")
        self.assertIn('data-page="sources"', body)
        self.assertIn('href="/sources"', body)
        self.assertIn("/v2/sources", body)

    def test_required_page_routes_return_html(self) -> None:
        pages = ("overview", "map", "events", "conflicts", "actors", "timeline", "alerts", "sources", "system")
        with running_server() as base:
            for page in pages:
                with self.subTest(page=page), urlopen(base + "/" + page) as response:
                    body = response.read().decode("utf-8")
                    self.assertEqual(200, response.status)
                    self.assertIn("Monitor de Conflitos", body)
                    self.assertIn("text/html", response.headers.get("Content-Type", ""))


@contextmanager
def running_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


if __name__ == "__main__":
    unittest.main()

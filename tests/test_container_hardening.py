from __future__ import annotations

import unittest
from pathlib import Path


class ContainerHardeningTests(unittest.TestCase):
    def test_production_container_is_non_root_and_not_editable_install(self) -> None:
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER 65532:65532", dockerfile)
        self.assertIn('pip install --no-cache-dir ".[production]"', dockerfile)
        self.assertNotIn("pip install -e", dockerfile)
        self.assertNotIn("COPY . /app", dockerfile)

    def test_production_container_applies_available_os_security_updates(self) -> None:
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("apt-get update", dockerfile)
        self.assertIn("apt-get upgrade -y --no-install-recommends", dockerfile)
        self.assertIn("rm -rf /var/lib/apt/lists/*", dockerfile)
        self.assertLess(dockerfile.index("apt-get upgrade"), dockerfile.index("pip install"))

    def test_docker_context_excludes_non_runtime_assets(self) -> None:
        ignore = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
        ignored = {line.strip() for line in ignore if line.strip() and not line.startswith("#")}
        for expected in {".git", ".github", "tests", "docs", "infra", "data", "generated", "artifacts"}:
            self.assertIn(expected, ignored)
        for required in {"config", "geowatch", "scripts", "sql"}:
            self.assertNotIn(required, ignored)


if __name__ == "__main__":
    unittest.main()

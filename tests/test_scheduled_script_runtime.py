from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class ScheduledScriptRuntimeTests(unittest.TestCase):
    def test_direct_scripts_bootstrap_repository_without_installed_package(self):
        root = Path(__file__).resolve().parents[1]
        scripts = [
            "build_ucdp_bulk_artifacts.py",
            "build_wpi_artifacts.py",
            "build_worldbank_artifacts.py",
            "build_sanctions_artifacts.py",
            "build_beta_summary.py",
        ]
        for name in scripts:
            script = root / "scripts" / name
            code = (
                "import runpy,sys; "
                f"sys.path=[{str(script.parent)!r}]+[p for p in sys.path if p not in ({str(root)!r}, '')]; "
                f"runpy.run_path({str(script)!r}, run_name='geowatch_import_smoke')"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=root.parent,
                text=True,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(
                0,
                result.returncode,
                f"{name} failed direct-import bootstrap:\nSTDOUT={result.stdout}\nSTDERR={result.stderr}",
            )


if __name__ == "__main__":
    unittest.main()

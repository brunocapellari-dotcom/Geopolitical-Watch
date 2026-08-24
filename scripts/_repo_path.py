from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_path() -> Path:
    """Make repository-root imports deterministic for direct script execution.

    GitHub Actions and local operators often execute ``python scripts/foo.py``.
    In that mode Python puts ``scripts/`` rather than the repository root at
    ``sys.path[0]``. This helper adds the root explicitly without requiring an
    editable install or a workflow-specific PYTHONPATH.
    """
    root = Path(__file__).resolve().parents[1]
    value = str(root)
    if value not in sys.path:
        sys.path.insert(0, value)
    return root

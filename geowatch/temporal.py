from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_payload(value: Any) -> tuple[str, str]:
    """Return deterministic JSON and SHA-256 for immutable point-in-time versions."""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = ["canonical_payload"]

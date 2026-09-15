from __future__ import annotations

import os

from .raw_store import raw_backend_name
from .storage_factory import backend_name

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
_MIN_PRODUCTION_SECRET_LENGTH = 32


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in _TRUE


def strict_production_mode() -> bool:
    """Enable strict startup automatically for published Replit deployments."""
    return _flag("GEOWATCH_STRICT_PRODUCTION") or os.environ.get("REPLIT_DEPLOYMENT") == "1"


def production_requirements() -> dict[str, bool]:
    token = os.environ.get("GEOWATCH_API_TOKEN", "")
    cookie_value = os.environ.get("GEOWATCH_COOKIE_SECURE", "1").strip().casefold()
    return {
        "private_auth_secret": len(token) >= _MIN_PRODUCTION_SECRET_LENGTH,
        "persistent_database": backend_name() == "postgresql-postgis",
        "persistent_raw_evidence": raw_backend_name() in {"postgresql-compressed", "gcs"},
        "embedded_collector": _flag("GEOWATCH_EMBEDDED_COLLECTOR"),
        "secure_cookie": cookie_value not in _FALSE,
    }


def validate_production_runtime() -> dict[str, bool]:
    """Raise before binding a public port when a production requirement is missing."""
    checks = production_requirements()
    if not strict_production_mode():
        return checks
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError(
            "Refusing to start incomplete production runtime; failed checks: "
            + ", ".join(failed)
        )
    return checks

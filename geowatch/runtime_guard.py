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
    """Enable strict startup for an explicitly published production runtime."""
    return _flag("GEOWATCH_STRICT_PRODUCTION")


def production_requirements() -> dict[str, bool]:
    token = os.environ.get("GEOWATCH_API_TOKEN", "")
    cookie_value = os.environ.get("GEOWATCH_COOKIE_SECURE", "1").strip().casefold()
    embedded = _flag("GEOWATCH_EMBEDDED_COLLECTOR")
    scheduler = _flag("GEOWATCH_SOURCE_SCHEDULER")
    external_scheduler = _flag("GEOWATCH_EXTERNAL_SCHEDULER")
    configured_paths = sum(1 for value in (embedded, scheduler, external_scheduler) if value)
    return {
        "private_auth_secret": len(token) >= _MIN_PRODUCTION_SECRET_LENGTH,
        "persistent_database": backend_name() == "postgresql-postgis",
        "persistent_raw_evidence": raw_backend_name() in {"postgresql-compressed", "gcs"},
        "collection_path_configured": configured_paths == 1,
        "duplicate_collectors_disabled": configured_paths <= 1,
        "secure_cookie": cookie_value not in _FALSE,
    }


def validate_production_runtime() -> dict[str, bool]:
    """Raise before binding a public port when a production requirement is missing.

    Exactly one batch collection mode is allowed. ``GEOWATCH_EXTERNAL_SCHEDULER``
    is the final cloud mode, where Cloud Scheduler invokes a short-lived Cloud Run
    Job using ``python -m geowatch scheduler-tick``. The in-process scheduler and
    embedded collector remain local/rollback modes only.
    """
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

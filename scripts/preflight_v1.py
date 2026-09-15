from __future__ import annotations

import json
import os
from pathlib import Path

REQUIRED_FILES = [
    "config/readiness.json",
    "sql/postgres_postgis.sql",
    "infra/gcp/main.tf",
    "infra/gcp/backend.tf",
    ".github/workflows/gcp-release.yml",
    "docs/STRATEGIC_INTELLIGENCE_MODEL.md",
    "config/geopolitics/country_registry.json",
    "config/geopolitics/critical_infrastructure.json",
    "config/geopolitics/forecast_templates.json",
]

# Generic/local preflight accepts a complete Postgres DSN. Google Cloud production
# uses split Secret Manager/Cloud SQL settings instead and is validated by the
# strict runtime + Terraform gate.
REQUIRED_PROD_ENV = ["GEOWATCH_DB_URL", "GEOWATCH_RAW_BUCKET", "GEOWATCH_API_TOKEN"]

# Credential contracts must mirror the canonical source adapters. ACLED supports
# an issued access token OR username/password; no fictitious client secret pair.
OPTIONAL_SOURCE_ENV = [
    "UCDP_API_TOKEN",
    "RELIEFWEB_APPNAME",
    "FIRMS_MAP_KEY",
    "ACLED_ACCESS_TOKEN",
    "ACLED_USERNAME",
    "ACLED_PASSWORD",
    "AISSTREAM_API_KEY",
]


def preflight() -> dict:
    files = {path: Path(path).exists() for path in REQUIRED_FILES}
    env = {key: bool(os.environ.get(key)) for key in REQUIRED_PROD_ENV}
    source_env = {key: bool(os.environ.get(key)) for key in OPTIONAL_SOURCE_ENV}
    acled_ready = source_env["ACLED_ACCESS_TOKEN"] or (
        source_env["ACLED_USERNAME"] and source_env["ACLED_PASSWORD"]
    )
    return {
        "schema_version": "geowatch-v1-preflight-v2",
        "repository_files": files,
        "production_environment": env,
        "source_credentials": source_env,
        "source_credential_sets": {"acled_ready": acled_ready},
        "repository_ready": all(files.values()),
        "production_env_ready": all(env.values()),
        "external_tests_required": [
            "live_production_smoke",
            "database_restore_drill",
            "historical_out_of_sample_validation",
            "security_and_source_rights_audit",
        ],
        "ready_for_v1": False,
        "notes": [
            "Passing repository/env checks alone is insufficient for v1.0.",
            "Secrets are checked only for presence; values are never printed.",
            "Terraform is the only infrastructure provisioning path; gcloud deployment scripts are intentionally not canonical.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(preflight(), ensure_ascii=False, indent=2))

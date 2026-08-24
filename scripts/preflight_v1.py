from __future__ import annotations

import json
import os
from pathlib import Path

REQUIRED_FILES=[
    "config/readiness.json","sql/postgres_postgis.sql","scripts/deploy_gcp.sh","docs/STRATEGIC_INTELLIGENCE_MODEL.md",
    "config/geopolitics/country_registry.json","config/geopolitics/critical_infrastructure.json","config/geopolitics/forecast_templates.json",
]
REQUIRED_PROD_ENV=["GEOWATCH_DB_URL","GEOWATCH_RAW_BUCKET","GEOWATCH_API_TOKEN"]
OPTIONAL_SOURCE_ENV=["UCDP_API_TOKEN","RELIEFWEB_APPNAME","FIRMS_MAP_KEY","ACLED_CLIENT_ID","ACLED_CLIENT_SECRET"]


def preflight()->dict:
    files={path:Path(path).exists() for path in REQUIRED_FILES}
    env={key:bool(os.environ.get(key)) for key in REQUIRED_PROD_ENV}
    source_env={key:bool(os.environ.get(key)) for key in OPTIONAL_SOURCE_ENV}
    return {
        "schema_version":"geowatch-v1-preflight-v1","repository_files":files,"production_environment":env,"source_credentials":source_env,
        "repository_ready":all(files.values()),"production_env_ready":all(env.values()),
        "external_tests_required":["live_production_smoke","database_restore_drill","historical_out_of_sample_validation","security_and_source_rights_audit"],
        "ready_for_v1":False,
        "notes":["Passing repository/env checks alone is insufficient for v1.0.","Secrets are checked only for presence; values are never printed."],
    }

if __name__=="__main__": print(json.dumps(preflight(),ensure_ascii=False,indent=2))

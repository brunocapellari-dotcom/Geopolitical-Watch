#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TEST_DB="${GEOWATCH_TEST_POSTGRES_URL:-${DATABASE_URL:-}}"
: "${TEST_DB:?GEOWATCH_TEST_POSTGRES_URL or DATABASE_URL is required}"

printf '\n== portable 1/8 compile/config/import ==\n'
python -m compileall -q geowatch scripts tests
python - <<'PY'
import importlib, json, pkgutil
from pathlib import Path
import geowatch
for path in sorted(Path("config").rglob("*.json")):
    with path.open(encoding="utf-8") as handle:
        json.load(handle)
modules = sorted(item.name for item in pkgutil.walk_packages(geowatch.__path__, geowatch.__name__ + "."))
for name in modules:
    importlib.import_module(name)
print(f"validated configs and imported {len(modules)} modules")
PY

printf '\n== portable 2/8 complete tests with coverage ==\n'
coverage erase
env -u DATABASE_URL -u GEOWATCH_DB_URL -u GEOWATCH_RAW_BACKEND -u GEOWATCH_RAW_BUCKET -u GEOWATCH_STRICT_PRODUCTION -u GEOWATCH_API_TOKEN -u GEOWATCH_SOURCE_SCHEDULER -u GEOWATCH_EXTERNAL_SCHEDULER -u GEOWATCH_EMBEDDED_COLLECTOR coverage run --source=geowatch -m unittest discover -s tests -v
coverage report -m

printf '\n== portable 3/8 deterministic fixtures ==\n'
python -m geowatch evaluate --fixture tests/fixtures/clustering_eval.json >/tmp/geowatch-portable-clustering.json
python -m geowatch evaluate-episodes --fixture tests/fixtures/episode_eval.json --entities config/entities.json >/tmp/geowatch-portable-episodes.json
python - <<'PY'
import json
from pathlib import Path
cluster=json.loads(Path("/tmp/geowatch-portable-clustering.json").read_text())
episode=json.loads(Path("/tmp/geowatch-portable-episodes.json").read_text())
assert cluster["pairwise_precision"] == cluster["pairwise_recall"] == 1.0
assert episode["pairwise_precision"] == episode["pairwise_recall"] == 1.0
assert episode["false_positive_pair_count"] == episode["missed_pair_count"] == 0
print("deterministic fixtures: ok")
PY

printf '\n== portable 4/8 dependency/static security ==\n'
pip-audit
bandit -q -r geowatch -x tests -ll -s B104,B608

printf '\n== portable 5/8 PostgreSQL/PostGIS/RAW/relationship schema ==\n'
GEOWATCH_DB_URL="$TEST_DB" GEOWATCH_RAW_BACKEND=postgres python - <<'PY'
from geowatch.raw_store import open_raw_store, raw_backend_name
from geowatch.storage_factory import backend_name, open_store
assert backend_name() == "postgresql-postgis"
raw = open_raw_store()
assert raw.get("portable-gate-schema-probe", "0" * 64) is None
store=open_store()
try:
    with store.db.cursor() as cur:
        cur.execute("SELECT PostGIS_Version() AS postgis_version")
        assert cur.fetchone()["postgis_version"]
        for table in (
            "relationships",
            "raw_payloads",
            "raw_evidence_observations",
            "raw_evidence_index",
            "events",
            "claims",
            "evidence",
            "source_checkpoints",
        ):
            cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{table}",))
            assert cur.fetchone()["relation"] == table, table
finally:
    store.close()
assert raw_backend_name() == "postgresql-compressed"
print("postgres/postgis/raw/relationships schema: ok (read-only)")
PY

printf '\n== portable 6/8 strict runtime invariants ==\n'
GEOWATCH_DB_URL="$TEST_DB" \
GEOWATCH_RAW_BACKEND=postgres \
GEOWATCH_API_TOKEN='portable-gate-only-secret-0123456789abcdef' \
GEOWATCH_EXTERNAL_SCHEDULER=1 \
GEOWATCH_SOURCE_SCHEDULER=0 \
GEOWATCH_EMBEDDED_COLLECTOR=0 \
GEOWATCH_COOKIE_SECURE=1 \
GEOWATCH_STRICT_PRODUCTION=1 \
python - <<'PY'
from geowatch.runtime_guard import validate_production_runtime
checks=validate_production_runtime()
assert all(checks.values()), checks
print("strict production guard: ok")
PY

printf '\n== portable 7/8 private HTTP smoke ==\n'
export GEOWATCH_DB_URL="$TEST_DB"
export GEOWATCH_RAW_BACKEND=postgres
export GEOWATCH_API_TOKEN='portable-gate-only-secret-0123456789abcdef'
export GEOWATCH_EXTERNAL_SCHEDULER=1
export GEOWATCH_SOURCE_SCHEDULER=0
export GEOWATCH_EMBEDDED_COLLECTOR=0
export GEOWATCH_COOKIE_SECURE=0
export GEOWATCH_WPI_RUNTIME=0
unset AISSTREAM_API_KEY || true
export HOST=127.0.0.1
export PORT=18080
unset GEOWATCH_STRICT_PRODUCTION || true
python -m geowatch serve >/tmp/geowatch-portable-gate-server.log 2>&1 &
pid=$!
cleanup() { kill "$pid" 2>/dev/null || true; }
trap cleanup EXIT
for _ in {1..40}; do
  if curl --fail --silent http://127.0.0.1:18080/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent http://127.0.0.1:18080/health | grep -q 'geopolitical-watch'
curl --fail --silent http://127.0.0.1:18080/dashboard | grep -q 'Acesso privado'
curl --fail --silent -H 'Authorization: Bearer portable-gate-only-secret-0123456789abcdef' \
  'http://127.0.0.1:18080/v2/relationships?limit=1' | grep -q 'geowatch-relationships-v1'

printf '\n== portable 8/8 browser smoke ==\n'
export GEOWATCH_E2E_URL='http://127.0.0.1:18080/'
export GEOWATCH_E2E_TOKEN='portable-gate-only-secret-0123456789abcdef'
python scripts/browser_smoke.py

printf '\nPORTABLE RUNTIME GATE: PASS\n'

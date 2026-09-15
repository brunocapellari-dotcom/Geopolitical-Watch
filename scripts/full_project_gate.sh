#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${GEOWATCH_TEST_POSTGRES_URL:?GEOWATCH_TEST_POSTGRES_URL is required for the full project gate}"

printf '\n== 1/12 compile entire repository ==\n'
python -m compileall -q geowatch scripts tests

printf '\n== 2/12 validate every JSON configuration file ==\n'
python - <<'PY'
import json
from pathlib import Path
files = sorted(Path('config').rglob('*.json'))
assert files, 'no JSON config files found'
for path in files:
    with path.open(encoding='utf-8') as handle:
        json.load(handle)
print(f'validated {len(files)} JSON files')
PY

printf '\n== 3/12 import every geowatch Python module ==\n'
python - <<'PY'
import importlib
import pkgutil
import geowatch
modules = sorted(item.name for item in pkgutil.walk_packages(geowatch.__path__, geowatch.__name__ + '.'))
failed = []
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:
        failed.append((name, type(exc).__name__, str(exc)))
if failed:
    raise SystemExit('module import failures: ' + repr(failed))
print(f'imported {len(modules)} modules')
PY

printf '\n== 4/12 run complete unit/contract suite with coverage collection ==\n'
coverage erase
coverage run --source=geowatch -m unittest discover -s tests -v
coverage report -m

printf '\n== 5/12 run deterministic evaluation fixtures ==\n'
python -m geowatch evaluate --fixture tests/fixtures/clustering_eval.json >/tmp/geowatch-clustering-eval.json
python -m geowatch evaluate-episodes --fixture tests/fixtures/episode_eval.json --entities config/entities.json >/tmp/geowatch-episode-eval.json
python - <<'PY'
import json
from pathlib import Path
cluster_path = Path('/tmp/geowatch-clustering-eval.json')
episode_path = Path('/tmp/geowatch-episode-eval.json')
cluster = json.loads(cluster_path.read_text(encoding='utf-8'))
episode = json.loads(episode_path.read_text(encoding='utf-8'))
assert cluster.get('pairwise_precision') == 1.0, cluster
assert cluster.get('pairwise_recall') == 1.0, cluster
assert episode.get('pairwise_precision') == 1.0, episode
assert episode.get('pairwise_recall') == 1.0, episode
assert episode.get('predicted_episodes') == episode.get('expected_episodes'), episode
assert episode.get('false_positive_pair_count') == 0, episode
assert episode.get('missed_pair_count') == 0, episode
print('evaluation fixtures: perfect deterministic scores')
PY

printf '\n== 6/12 audit dependencies ==\n'
pip-audit

printf '\n== 7/12 static security analysis ==\n'
bandit -q -r geowatch -x tests -ll -s B104,B608

printf '\n== 8/12 validate PostgreSQL/PostGIS and persistent RAW backend ==\n'
GEOWATCH_DB_URL="$GEOWATCH_TEST_POSTGRES_URL" GEOWATCH_RAW_BACKEND=postgres python - <<'PY'
from geowatch.storage_factory import backend_name, open_store
from geowatch.raw_store import open_raw_store, raw_backend_name
assert backend_name() == 'postgresql-postgis'
store = open_store()
try:
    with store.db.cursor() as cur:
        cur.execute('SELECT PostGIS_Version() AS postgis_version')
        row = cur.fetchone()
        assert row and row.get('postgis_version'), row
finally:
    store.close()
raw = open_raw_store()
ref, digest = raw.put('full-gate', '2026-09-15T00:00:00+00:00', b'geowatch-full-project-gate', 'txt')
assert ref.startswith('pgraw://')
assert raw.get('full-gate', digest) == b'geowatch-full-project-gate'
assert raw_backend_name() == 'postgresql-compressed'
print('postgres/postgis/raw: ok')
PY

printf '\n== 9/12 strict production invariants ==\n'
GEOWATCH_DB_URL="$GEOWATCH_TEST_POSTGRES_URL" \
GEOWATCH_RAW_BACKEND=postgres \
GEOWATCH_API_TOKEN='full-project-gate-secret-0123456789abcdef' \
GEOWATCH_EXTERNAL_SCHEDULER=1 \
GEOWATCH_SOURCE_SCHEDULER=0 \
GEOWATCH_EMBEDDED_COLLECTOR=0 \
GEOWATCH_COOKIE_SECURE=1 \
GEOWATCH_STRICT_PRODUCTION=1 \
python - <<'PY'
from geowatch.runtime_guard import validate_production_runtime
checks=validate_production_runtime()
assert all(checks.values()), checks
print('strict production guard: ok')
PY

printf '\n== 10/12 Terraform format/init/validate ==\n'
terraform fmt -check -recursive infra/gcp
terraform -chdir=infra/gcp init -backend=false -input=false >/tmp/geowatch-terraform-init.log
terraform -chdir=infra/gcp validate

printf '\n== 11/12 build production container ==\n'
docker build --pull -t geowatch-full-gate:local .

printf '\n== 12/12 private HTTP + real browser MapLibre smoke ==\n'
export GEOWATCH_DB_URL="$GEOWATCH_TEST_POSTGRES_URL"
export GEOWATCH_RAW_BACKEND=postgres
export GEOWATCH_API_TOKEN='full-project-gate-secret-0123456789abcdef'
export GEOWATCH_EXTERNAL_SCHEDULER=1
export GEOWATCH_SOURCE_SCHEDULER=0
export GEOWATCH_EMBEDDED_COLLECTOR=0
export GEOWATCH_COOKIE_SECURE=0
export GEOWATCH_WPI_RUNTIME=0
export HOST=127.0.0.1
export PORT=8080
unset AISSTREAM_API_KEY || true
unset GEOWATCH_STRICT_PRODUCTION || true

python -m geowatch serve >/tmp/geowatch-full-gate-server.log 2>&1 &
pid=$!
cleanup() { kill "$pid" 2>/dev/null || true; }
trap cleanup EXIT
for _ in {1..40}; do
  if curl --fail --silent http://127.0.0.1:8080/health >/tmp/geowatch-health.json; then
    break
  fi
  sleep 0.5
done
curl --fail --silent http://127.0.0.1:8080/health | grep -q 'geopolitical-watch'
curl --fail --silent http://127.0.0.1:8080/dashboard | grep -q 'Acesso privado'
curl --fail --silent -D /tmp/geowatch-login.headers -o /tmp/geowatch-login.body -X POST \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'password=full-project-gate-secret-0123456789abcdef' \
  http://127.0.0.1:8080/login
grep -qi 'set-cookie: geowatch_session=' /tmp/geowatch-login.headers
grep -qi 'content-security-policy:.*worker-src.*blob:' /tmp/geowatch-login.headers
grep -qi 'x-content-type-options: nosniff' /tmp/geowatch-login.headers
grep -qi 'x-frame-options: DENY' /tmp/geowatch-login.headers
! grep -qi 'Python/' /tmp/geowatch-login.headers

export GEOWATCH_E2E_URL='http://127.0.0.1:8080/'
export GEOWATCH_E2E_TOKEN='full-project-gate-secret-0123456789abcdef'
python scripts/browser_smoke.py

printf '\nFULL PROJECT GATE: PASS\n'

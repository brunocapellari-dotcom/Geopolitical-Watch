#!/usr/bin/env bash
set -euo pipefail

: "${GEOWATCH_BASE_URL:?Set GEOWATCH_BASE_URL}"
: "${GEOWATCH_API_TOKEN:?Set GEOWATCH_API_TOKEN}"

request() {
  local path="$1"
  curl --fail --silent --show-error \
    -H "Authorization: Bearer ${GEOWATCH_API_TOKEN}" \
    -H 'Accept: application/json' \
    "${GEOWATCH_BASE_URL%/}${path}"
}

health="$(curl --fail --silent --show-error "${GEOWATCH_BASE_URL%/}/health")"
python -c 'import json,sys; x=json.load(sys.stdin); assert x["status"]=="ok"; assert x["version"].startswith("0.") or x["version"].startswith("1.")' <<<"${health}"

request /v2/operational | python -c 'import json,sys; x=json.load(sys.stdin); assert isinstance(x,dict)'
request /v2/readiness | python -c 'import json,sys; x=json.load(sys.stdin); assert x.get("readiness_not_accuracy") is True'
request /v2/coverage | python -c 'import json,sys; x=json.load(sys.stdin); assert x.get("schema_version")=="geowatch-coverage-inventory-v1"'
request /v2/geopolitics/graph | python -c 'import json,sys; x=json.load(sys.stdin); assert isinstance(x,dict)'
request /v2/consumers/agrolog/feed | python -c 'import json,sys; x=json.load(sys.stdin); assert isinstance(x,dict)'

echo "Production smoke gate passed for API surfaces."
echo "This does not by itself prove database restore, source licensing, or analytical accuracy."

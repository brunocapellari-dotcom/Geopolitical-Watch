#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-holding-prod-bc}"
REGION="${REGION:-southamerica-east1}"
REPO="${REPO:-brunocapellari-dotcom/Geopolitical-Watch}"
STATE_BUCKET="${STATE_BUCKET:-${PROJECT_ID}-geowatch-tfstate}"
APPLY="${APPLY:-0}"
RELEASE_REF="${RELEASE_REF:-stabilization/go-live-20261007}"

log() { printf '\n[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { echo "$*" >&2; exit 1; }

command -v gcloud >/dev/null || die "gcloud CLI is required. Use Google Cloud Shell or install gcloud."
command -v terraform >/dev/null || die "Terraform >=1.11 is required."

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
test -n "$ACTIVE_ACCOUNT" || die "No active gcloud account."

log "Using project $PROJECT_ID as $ACTIVE_ACCOUNT"
gcloud config set project "$PROJECT_ID" >/dev/null

log "Ensuring bootstrap APIs"
gcloud services enable   storage.googleapis.com   serviceusage.googleapis.com   iam.googleapis.com   iamcredentials.googleapis.com   sts.googleapis.com   cloudbuild.googleapis.com   --project="$PROJECT_ID" >/dev/null

if ! gcloud storage buckets describe "gs://$STATE_BUCKET" --project="$PROJECT_ID" >/dev/null 2>&1; then
  log "Creating dedicated private Terraform state bucket"
  gcloud storage buckets create "gs://$STATE_BUCKET"     --project="$PROJECT_ID"     --location="$REGION"     --uniform-bucket-level-access     --public-access-prevention
fi
gcloud storage buckets update "gs://$STATE_BUCKET" --versioning >/dev/null

secret_or_random() {
  local secret_id="$1"
  local bytes="$2"
  local value=""
  value="$(gcloud secrets versions access latest --secret="$secret_id" --project="$PROJECT_ID" 2>/dev/null || true)"
  if [ -z "$value" ]; then
    value="$(python - "$bytes" <<'PY'
import secrets, sys
print(secrets.token_urlsafe(int(sys.argv[1])))
PY
)"
  fi
  printf '%s' "$value"
}

export TF_VAR_project_id="$PROJECT_ID"
export TF_VAR_region="$REGION"
export TF_VAR_deploy_runtime=false
export TF_VAR_api_token="${TF_VAR_api_token:-$(secret_or_random geowatch-api-token 48)}"
export TF_VAR_db_password="${TF_VAR_db_password:-$(secret_or_random geowatch-db-password 36)}"
export TF_VAR_aisstream_api_key="${TF_VAR_aisstream_api_key:-}"

log "Initializing canonical Terraform foundation state"
terraform -chdir=infra/gcp init -reconfigure   -backend-config="bucket=$STATE_BUCKET"   -input=false

log "Formatting and validating infrastructure"
terraform -chdir=infra/gcp fmt -check -diff -recursive
terraform -chdir=infra/gcp validate

PLAN="/tmp/geowatch-foundation.tfplan"
PLAN_JSON="/tmp/geowatch-foundation-plan.json"

log "Planning foundation only; runtime remains disabled"
terraform -chdir=infra/gcp plan   -input=false   -out="$PLAN"
terraform -chdir=infra/gcp show -json "$PLAN" > "$PLAN_JSON"

python - "$PLAN_JSON" <<'PY'
import json, sys
payload=json.load(open(sys.argv[1], encoding="utf-8"))
destructive=[]
for row in payload.get("resource_changes", []):
    actions=((row.get("change") or {}).get("actions") or [])
    if "delete" in actions:
        destructive.append({"address":row.get("address"),"actions":actions})
if destructive:
    raise SystemExit("Refusing destructive foundation plan: " + json.dumps(destructive))
print("non-destructive foundation plan: ok")
PY

if [ "$APPLY" != "1" ]; then
  cat <<EOF

PLAN READY — NOT APPLIED

No billable Geopolitical-Watch foundation resource was created by Terraform in this run.
Review the plan above. To apply the exact non-destructive foundation:

  APPLY=1 bash scripts/bootstrap_gcp_federation.sh

This foundation can create billable resources, especially Cloud SQL.
EOF
  exit 0
fi

log "Applying reviewed foundation"
terraform -chdir=infra/gcp apply -auto-approve "$PLAN"

WIF_PROVIDER="$(terraform -chdir=infra/gcp output -raw github_workload_identity_provider)"
DEPLOY_SA="$(terraform -chdir=infra/gcp output -raw github_deployer_service_account)"
test -n "$WIF_PROVIDER"
test -n "$DEPLOY_SA"

cat <<EOF

FOUNDATION READY

GCP_PROJECT_ID=$PROJECT_ID
GCP_REGION=$REGION
GCP_WIF_PROVIDER=$WIF_PROVIDER
GCP_BUILD_SERVICE_ACCOUNT=$DEPLOY_SA
GCP_DEPLOY_SERVICE_ACCOUNT=$DEPLOY_SA
TF_STATE_BUCKET=$STATE_BUCKET

No long-lived service-account key was created.
Terraform remains the source of truth for WIF, IAM and production infrastructure.
EOF

if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  log "Publishing non-secret GitHub repository variables"
  printf '%s' "$PROJECT_ID" | gh variable set GCP_PROJECT_ID --repo "$REPO"
  printf '%s' "$REGION" | gh variable set GCP_REGION --repo "$REPO"
  printf '%s' "$WIF_PROVIDER" | gh variable set GCP_WIF_PROVIDER --repo "$REPO"
  printf '%s' "$DEPLOY_SA" | gh variable set GCP_BUILD_SERVICE_ACCOUNT --repo "$REPO"
  printf '%s' "$DEPLOY_SA" | gh variable set GCP_DEPLOY_SERVICE_ACCOUNT --repo "$REPO"

  log "Triggering the canonical Cloud Build gate on $RELEASE_REF"
  gh workflow run gcp-cloudbuild-gate.yml --repo "$REPO" --ref "$RELEASE_REF"
else
  cat <<EOF

GitHub CLI is not authenticated. Add the five non-secret values above under:
Repository -> Settings -> Secrets and variables -> Actions -> Variables.
EOF
fi

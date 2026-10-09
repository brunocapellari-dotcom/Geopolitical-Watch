#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-holding-prod-bc}"
REGION="${REGION:-southamerica-east1}"
REPO="${REPO:-brunocapellari-dotcom/Geopolitical-Watch}"
POOL_ID="${POOL_ID:-geowatch-github}"
PROVIDER_ID="${PROVIDER_ID:-github}"
DEPLOY_SA_ID="${DEPLOY_SA_ID:-geowatch-github-deployer}"
STABILIZATION_REF="${STABILIZATION_REF:-refs/heads/stabilization/go-live-20261007}"
RELEASE_REF="${RELEASE_REF:-refs/heads/release/go-live-20260929}"
MAIN_REF="refs/heads/main"

log() { printf '\n[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

command -v gcloud >/dev/null || {
  echo "gcloud CLI is required. Run this script from Google Cloud Shell or a workstation with gcloud installed." >&2
  exit 1
}

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
test -n "$ACTIVE_ACCOUNT" || {
  echo "No active gcloud account. Authenticate with your Google account first." >&2
  exit 1
}

log "Using project $PROJECT_ID as $ACTIVE_ACCOUNT"
gcloud config set project "$PROJECT_ID" >/dev/null

log "Ensuring identity and Cloud Build APIs"
gcloud services enable   iam.googleapis.com   iamcredentials.googleapis.com   sts.googleapis.com   cloudbuild.googleapis.com   serviceusage.googleapis.com   --project="$PROJECT_ID" >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
test -n "$PROJECT_NUMBER"
DEPLOY_SA_EMAIL="${DEPLOY_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$DEPLOY_SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  log "Creating dedicated Geopolitical-Watch GitHub service account"
  gcloud iam service-accounts create "$DEPLOY_SA_ID"     --project="$PROJECT_ID"     --display-name="Geopolitical Watch GitHub deployer"
else
  log "Dedicated Geopolitical-Watch service account already exists"
fi

if ! gcloud iam workload-identity-pools describe "$POOL_ID"   --project="$PROJECT_ID" --location=global >/dev/null 2>&1; then
  log "Creating dedicated Workload Identity Pool"
  gcloud iam workload-identity-pools create "$POOL_ID"     --project="$PROJECT_ID"     --location=global     --display-name="Geopolitical Watch GitHub"
else
  log "Workload Identity Pool already exists"
fi

MAPPING="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref"
CONDITION="assertion.repository == '${REPO}' && (assertion.ref == '${MAIN_REF}' || assertion.ref == '${RELEASE_REF}' || assertion.ref == '${STABILIZATION_REF}')"

if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID"   --workload-identity-pool="$POOL_ID"   --location=global   --project="$PROJECT_ID" >/dev/null 2>&1; then
  log "Creating GitHub OIDC provider with repository/ref restriction"
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID"     --workload-identity-pool="$POOL_ID"     --location=global     --project="$PROJECT_ID"     --display-name="Geopolitical Watch GitHub"     --issuer-uri="https://token.actions.githubusercontent.com"     --attribute-mapping="$MAPPING"     --attribute-condition="$CONDITION"
else
  log "Reconciling GitHub OIDC provider restriction"
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID"     --workload-identity-pool="$POOL_ID"     --location=global     --project="$PROJECT_ID"     --issuer-uri="https://token.actions.githubusercontent.com"     --attribute-mapping="$MAPPING"     --attribute-condition="$CONDITION"
fi

POOL_NAME="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
PROVIDER_NAME="${POOL_NAME}/providers/${PROVIDER_ID}"
PRINCIPAL="principalSet://iam.googleapis.com/${POOL_NAME}/attribute.repository/${REPO}"

log "Granting keyless impersonation to the dedicated deployer"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA_EMAIL"   --project="$PROJECT_ID"   --role="roles/iam.workloadIdentityUser"   --member="$PRINCIPAL" >/dev/null

log "Granting only the role required to submit the current Cloud Build gate"
gcloud projects add-iam-policy-binding "$PROJECT_ID"   --member="serviceAccount:${DEPLOY_SA_EMAIL}"   --role="roles/cloudbuild.builds.editor"   --condition=None >/dev/null

cat <<EOF

GCP FEDERATION READY

GCP_PROJECT_ID=$PROJECT_ID
GCP_REGION=$REGION
GCP_WIF_PROVIDER=$PROVIDER_NAME
GCP_BUILD_SERVICE_ACCOUNT=$DEPLOY_SA_EMAIL
GCP_DEPLOY_SERVICE_ACCOUNT=$DEPLOY_SA_EMAIL

No service-account key was created.
The provider is restricted to:
  $REPO
  $MAIN_REF
  $RELEASE_REF
  $STABILIZATION_REF
EOF

if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  log "Publishing non-secret GitHub repository variables"
  printf '%s' "$PROJECT_ID" | gh variable set GCP_PROJECT_ID --repo "$REPO"
  printf '%s' "$REGION" | gh variable set GCP_REGION --repo "$REPO"
  printf '%s' "$PROVIDER_NAME" | gh variable set GCP_WIF_PROVIDER --repo "$REPO"
  printf '%s' "$DEPLOY_SA_EMAIL" | gh variable set GCP_BUILD_SERVICE_ACCOUNT --repo "$REPO"
  printf '%s' "$DEPLOY_SA_EMAIL" | gh variable set GCP_DEPLOY_SERVICE_ACCOUNT --repo "$REPO"
  log "GitHub variables published"
else
  cat <<EOF

GitHub CLI is not authenticated, so repository variables were not changed.
Add the five non-secret values printed above under:
GitHub repository -> Settings -> Secrets and variables -> Actions -> Variables.
EOF
fi

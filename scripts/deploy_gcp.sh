#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-southamerica-east1}"
AR_REPO="${AR_REPO:-geowatch}"
API_SERVICE="${API_SERVICE:-geowatch-api}"
COLLECTOR_JOB="${COLLECTOR_JOB:-geowatch-collector}"
DISPATCH_JOB="${DISPATCH_JOB:-geowatch-alert-dispatch}"
SCHEDULER_JOB="${SCHEDULER_JOB:-geowatch-collector-hourly}"
DISPATCH_SCHEDULER_JOB="${DISPATCH_SCHEDULER_JOB:-geowatch-alert-dispatch-hourly}"
RUNTIME_SA="${RUNTIME_SA:-geowatch-runtime}"
SCHEDULER_SA="${SCHEDULER_SA:-geowatch-scheduler}"
RAW_BUCKET="${RAW_BUCKET:-${PROJECT_ID}-geowatch-raw}"
DB_URL_SECRET="${DB_URL_SECRET:-geowatch-db-url}"
API_TOKEN_SECRET="${API_TOKEN_SECRET:-geowatch-api-token}"
WEBHOOK_URL_SECRET="${WEBHOOK_URL_SECRET:-}"
WEBHOOK_TOKEN_SECRET="${WEBHOOK_TOKEN_SECRET:-}"
SCHEDULE="${SCHEDULE:-5 * * * *}"
DISPATCH_SCHEDULE="${DISPATCH_SCHEDULE:-15 * * * *}"
TIME_ZONE="${TIME_ZONE:-America/Cuiaba}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/geowatch:latest"

command -v gcloud >/dev/null || { echo "gcloud CLI not found" >&2; exit 1; }

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud services enable \
  run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com cloudscheduler.googleapis.com storage.googleapis.com

if ! gcloud artifacts repositories describe "${AR_REPO}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPO}" --repository-format=docker --location "${REGION}"
fi

gcloud builds submit --tag "${IMAGE}" .

for SA in "${RUNTIME_SA}" "${SCHEDULER_SA}"; do
  if ! gcloud iam service-accounts describe "${SA}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${SA}"
  fi
done
RUNTIME_EMAIL="${RUNTIME_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_EMAIL="${SCHEDULER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud storage buckets describe "gs://${RAW_BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${RAW_BUCKET}" --location="${REGION}" --uniform-bucket-level-access
fi

gcloud storage buckets add-iam-policy-binding "gs://${RAW_BUCKET}" \
  --member="serviceAccount:${RUNTIME_EMAIL}" --role="roles/storage.objectAdmin" >/dev/null

for SECRET in "${DB_URL_SECRET}" "${API_TOKEN_SECRET}"; do
  gcloud secrets describe "${SECRET}" >/dev/null 2>&1 || {
    echo "Required Secret Manager secret '${SECRET}' does not exist. Create it before deployment." >&2
    exit 2
  }
  gcloud secrets add-iam-policy-binding "${SECRET}" \
    --member="serviceAccount:${RUNTIME_EMAIL}" --role="roles/secretmanager.secretAccessor" >/dev/null
done

gcloud run deploy "${API_SERVICE}" \
  --image="${IMAGE}" --region="${REGION}" --service-account="${RUNTIME_EMAIL}" \
  --no-allow-unauthenticated \
  --set-env-vars="GEOWATCH_RAW_BUCKET=${RAW_BUCKET}" \
  --set-secrets="GEOWATCH_DB_URL=${DB_URL_SECRET}:latest,GEOWATCH_API_TOKEN=${API_TOKEN_SECRET}:latest"

upsert_job() {
  local job="$1"; shift
  if gcloud run jobs describe "${job}" --region="${REGION}" >/dev/null 2>&1; then
    gcloud run jobs update "${job}" --region="${REGION}" --image="${IMAGE}" --service-account="${RUNTIME_EMAIL}" "$@"
  else
    gcloud run jobs create "${job}" --region="${REGION}" --image="${IMAGE}" --service-account="${RUNTIME_EMAIL}" "$@"
  fi
}

upsert_job "${COLLECTOR_JOB}" \
  --command=python --args=-m,geowatch,collect \
  --set-env-vars="GEOWATCH_RAW_BUCKET=${RAW_BUCKET}" \
  --set-secrets="GEOWATCH_DB_URL=${DB_URL_SECRET}:latest,GEOWATCH_API_TOKEN=${API_TOKEN_SECRET}:latest"

gcloud run jobs add-iam-policy-binding "${COLLECTOR_JOB}" --region="${REGION}" \
  --member="serviceAccount:${SCHEDULER_EMAIL}" --role="roles/run.invoker" >/dev/null

upsert_scheduler() {
  local name="$1" schedule="$2" job="$3"
  local uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${job}:run"
  if gcloud scheduler jobs describe "${name}" --location="${REGION}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${name}" --location="${REGION}" \
      --schedule="${schedule}" --time-zone="${TIME_ZONE}" --uri="${uri}" --http-method=POST \
      --oauth-service-account-email="${SCHEDULER_EMAIL}"
  else
    gcloud scheduler jobs create http "${name}" --location="${REGION}" \
      --schedule="${schedule}" --time-zone="${TIME_ZONE}" --uri="${uri}" --http-method=POST \
      --oauth-service-account-email="${SCHEDULER_EMAIL}"
  fi
}

upsert_scheduler "${SCHEDULER_JOB}" "${SCHEDULE}" "${COLLECTOR_JOB}"

if [[ -n "${WEBHOOK_URL_SECRET}" ]]; then
  gcloud secrets describe "${WEBHOOK_URL_SECRET}" >/dev/null 2>&1 || {
    echo "Webhook URL secret '${WEBHOOK_URL_SECRET}' does not exist." >&2
    exit 3
  }
  gcloud secrets add-iam-policy-binding "${WEBHOOK_URL_SECRET}" \
    --member="serviceAccount:${RUNTIME_EMAIL}" --role="roles/secretmanager.secretAccessor" >/dev/null

  DISPATCH_SECRETS="GEOWATCH_DB_URL=${DB_URL_SECRET}:latest,GEOWATCH_WEBHOOK_URL=${WEBHOOK_URL_SECRET}:latest"
  if [[ -n "${WEBHOOK_TOKEN_SECRET}" ]]; then
    gcloud secrets describe "${WEBHOOK_TOKEN_SECRET}" >/dev/null 2>&1 || {
      echo "Webhook token secret '${WEBHOOK_TOKEN_SECRET}' does not exist." >&2
      exit 4
    }
    gcloud secrets add-iam-policy-binding "${WEBHOOK_TOKEN_SECRET}" \
      --member="serviceAccount:${RUNTIME_EMAIL}" --role="roles/secretmanager.secretAccessor" >/dev/null
    DISPATCH_SECRETS="${DISPATCH_SECRETS},GEOWATCH_WEBHOOK_TOKEN=${WEBHOOK_TOKEN_SECRET}:latest"
  fi

  upsert_job "${DISPATCH_JOB}" \
    --command=python --args=-m,geowatch,dispatch-alerts \
    --set-secrets="${DISPATCH_SECRETS}"

  gcloud run jobs add-iam-policy-binding "${DISPATCH_JOB}" --region="${REGION}" \
    --member="serviceAccount:${SCHEDULER_EMAIL}" --role="roles/run.invoker" >/dev/null
  upsert_scheduler "${DISPATCH_SCHEDULER_JOB}" "${DISPATCH_SCHEDULE}" "${DISPATCH_JOB}"
else
  echo "WEBHOOK_URL_SECRET not set; alert outbox is enabled but external dispatcher scheduling is skipped."
fi

echo "Deployment assets configured. Required live validation:"
echo "  gcloud run jobs execute ${COLLECTOR_JOB} --region=${REGION} --wait"
if [[ -n "${WEBHOOK_URL_SECRET}" ]]; then
  echo "  gcloud run jobs execute ${DISPATCH_JOB} --region=${REGION} --wait"
fi
echo "Then inspect authenticated /health, /v2/operational, /v2/map and the configured consumer feed."

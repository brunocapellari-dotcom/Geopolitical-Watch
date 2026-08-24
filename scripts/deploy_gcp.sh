#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-southamerica-east1}"
AR_REPO="${AR_REPO:-geowatch}"
API_SERVICE="${API_SERVICE:-geowatch-api}"
COLLECTOR_JOB="${COLLECTOR_JOB:-geowatch-collector}"
SCHEDULER_JOB="${SCHEDULER_JOB:-geowatch-collector-hourly}"
RUNTIME_SA="${RUNTIME_SA:-geowatch-runtime}"
SCHEDULER_SA="${SCHEDULER_SA:-geowatch-scheduler}"
RAW_BUCKET="${RAW_BUCKET:-${PROJECT_ID}-geowatch-raw}"
DB_URL_SECRET="${DB_URL_SECRET:-geowatch-db-url}"
API_TOKEN_SECRET="${API_TOKEN_SECRET:-geowatch-api-token}"
SCHEDULE="${SCHEDULE:-5 * * * *}"
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

if gcloud run jobs describe "${COLLECTOR_JOB}" --region="${REGION}" >/dev/null 2>&1; then
  gcloud run jobs update "${COLLECTOR_JOB}" --region="${REGION}" --image="${IMAGE}" \
    --service-account="${RUNTIME_EMAIL}" --command=python --args=-m,geowatch,collect \
    --set-env-vars="GEOWATCH_RAW_BUCKET=${RAW_BUCKET}" \
    --set-secrets="GEOWATCH_DB_URL=${DB_URL_SECRET}:latest,GEOWATCH_API_TOKEN=${API_TOKEN_SECRET}:latest"
else
  gcloud run jobs create "${COLLECTOR_JOB}" --region="${REGION}" --image="${IMAGE}" \
    --service-account="${RUNTIME_EMAIL}" --command=python --args=-m,geowatch,collect \
    --set-env-vars="GEOWATCH_RAW_BUCKET=${RAW_BUCKET}" \
    --set-secrets="GEOWATCH_DB_URL=${DB_URL_SECRET}:latest,GEOWATCH_API_TOKEN=${API_TOKEN_SECRET}:latest"
fi

gcloud run jobs add-iam-policy-binding "${COLLECTOR_JOB}" --region="${REGION}" \
  --member="serviceAccount:${SCHEDULER_EMAIL}" --role="roles/run.invoker" >/dev/null

RUN_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${COLLECTOR_JOB}:run"
if gcloud scheduler jobs describe "${SCHEDULER_JOB}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "${SCHEDULER_JOB}" --location="${REGION}" \
    --schedule="${SCHEDULE}" --time-zone="${TIME_ZONE}" --uri="${RUN_URI}" --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_EMAIL}"
else
  gcloud scheduler jobs create http "${SCHEDULER_JOB}" --location="${REGION}" \
    --schedule="${SCHEDULE}" --time-zone="${TIME_ZONE}" --uri="${RUN_URI}" --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_EMAIL}"
fi

echo "Deployment configured. Run the collector smoke test:"
echo "  gcloud run jobs execute ${COLLECTOR_JOB} --region=${REGION} --wait"
echo "Then inspect API health through an authenticated Cloud Run request."

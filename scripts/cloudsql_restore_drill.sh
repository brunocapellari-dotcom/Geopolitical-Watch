#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
: "${SOURCE_INSTANCE:?Set SOURCE_INSTANCE}"
REGION="${REGION:-southamerica-east1}"
DRILL_INSTANCE="${DRILL_INSTANCE:-${SOURCE_INSTANCE}-restore-drill}"
APPLY="${APPLY:-0}"

command -v gcloud >/dev/null || { echo "gcloud CLI not found" >&2; exit 1; }
gcloud config set project "${PROJECT_ID}" >/dev/null

echo "Restore drill plan:"
echo "  project=${PROJECT_ID}"
echo "  source_instance=${SOURCE_INSTANCE}"
echo "  drill_instance=${DRILL_INSTANCE}"
echo "  region=${REGION}"
echo "  mode=$([[ ${APPLY} == 1 ]] && echo APPLY || echo DRY_RUN)"

gcloud sql instances describe "${SOURCE_INSTANCE}" --format='value(name)' >/dev/null
LATEST_BACKUP="$(gcloud sql backups list --instance="${SOURCE_INSTANCE}" --filter='status=SUCCESSFUL' --sort-by='~endTime' --limit=1 --format='value(id)')"
if [[ -z "${LATEST_BACKUP}" ]]; then
  echo "No successful backup found." >&2
  exit 2
fi
echo "  latest_successful_backup=${LATEST_BACKUP}"

if [[ "${APPLY}" != "1" ]]; then
  echo "Dry-run complete. Set APPLY=1 to create the isolated drill clone."
  exit 0
fi

if gcloud sql instances describe "${DRILL_INSTANCE}" >/dev/null 2>&1; then
  echo "Drill instance already exists; refusing to overwrite it." >&2
  exit 3
fi

gcloud sql instances clone "${SOURCE_INSTANCE}" "${DRILL_INSTANCE}"

gcloud sql instances describe "${DRILL_INSTANCE}" --format='json(name,state,region,databaseVersion,settings.backupConfiguration)' > /tmp/geowatch-restore-drill-instance.json

echo "Clone created. Required validation before marking the gate passed:"
echo "  1. connect using a temporary least-privilege account;"
echo "  2. run migrations/schema checks;"
echo "  3. verify event/episode/claim/evidence/checkpoint counts;"
echo "  4. run API smoke tests against the clone;"
echo "  5. record evidence in the recovery audit;"
echo "  6. delete the drill instance after validation."
echo "No automatic deletion is performed by this script."

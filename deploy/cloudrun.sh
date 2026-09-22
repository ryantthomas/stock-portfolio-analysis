#!/usr/bin/env bash
#
# Deploy to Google Cloud Run.
#
#   ./deploy/cloudrun.sh my-gcp-project
#
# Cloud Run builds the Dockerfile with Cloud Build, so there is nothing to
# push by hand. First run takes a few minutes; later ones are quicker.

set -euo pipefail

PROJECT="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
SERVICE="${SERVICE:-portfolio-analysis}"
REGION="${REGION:-us-central1}"

if [[ -z "$PROJECT" ]]; then
  echo "Usage: $0 <gcp-project-id>" >&2
  echo "   or: GOOGLE_CLOUD_PROJECT=<id> $0" >&2
  exit 1
fi

echo "Deploying '$SERVICE' to project '$PROJECT' in $REGION"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com cloudresourcemanager.googleapis.com \
  --project "$PROJECT"

# Source deploys are built by the project's default Compute Engine service
# account. Projects created since 2024 no longer grant it anything by default,
# so the build fails with PERMISSION_DENIED reading the uploaded source. Give
# it the purpose-built Cloud Run Builder role, once. Idempotent.
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
BUILD_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

if gcloud projects get-iam-policy "$PROJECT" \
     --flatten="bindings[].members" \
     --filter="bindings.role=roles/run.builder AND bindings.members=serviceAccount:${BUILD_SA}" \
     --format="value(bindings.role)" | grep -q "roles/run.builder"; then
  echo "Build service account already has the Cloud Run Builder role."
else
  echo "Granting the Cloud Run Builder role to ${BUILD_SA} (one-time setup)..."
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${BUILD_SA}" \
    --role="roles/run.builder" \
    --condition=None --quiet >/dev/null
  # IAM changes take a little while to reach Cloud Build; deploying straight
  # away can fail with the same error the grant just fixed.
  echo "Waiting 60s for the permission to take effect..."
  sleep 60
fi

gcloud run deploy "$SERVICE" \
  `# Accept the one-time prompt to create the Artifact Registry repository` \
  `# that holds the built image, so the script runs start to finish.` \
  --quiet \
  --project "$PROJECT" \
  --region "$REGION" \
  --source . \
  --allow-unauthenticated \
  `# Measured peak is ~120MB for 25 holdings over 10 years, so 512Mi is` \
  `# comfortable. Cloud Run bills for memory only while a request is in` \
  `# flight, so a larger size costs nothing when idle -- but it does raise` \
  `# the per-request price, and this app does not need it.` \
  --memory 512Mi \
  --cpu 1 \
  `# Scale to zero: no traffic, no charge. The cost is a ~2-4s cold start` \
  `# on the first request after an idle period.` \
  --min-instances 0 \
  `# The single most important cost guard: it bounds the worst case to one` \
  `# machine. One instance handling 20 requests at once is far more than a` \
  `# personal site needs, and a single process also makes the per-IP rate` \
  `# limiter exact rather than per-replica.` \
  --max-instances 1 \
  --concurrency 20 \
  --timeout 60 \
  --set-env-vars "PORTFOLIO_PROVIDER=auto,\
PORTFOLIO_ENABLE_WAREHOUSE_API=false,\
PORTFOLIO_PERSIST_PORTFOLIOS=false,\
PORTFOLIO_RATE_LIMIT_PER_MINUTE=30,\
PORTFOLIO_DUCKDB_PATH=/tmp/warehouse.duckdb"

# Every deploy stores a new image. Storage beyond the free allowance is only
# cents, but it grows forever unless pruned, so keep the two newest images
# (the live one plus one to roll back to) and delete the rest. Best-effort:
# a failure here never affects the running site.
POLICY_FILE="$(mktemp)"
cat > "$POLICY_FILE" <<'JSON'
[
  {"name": "keep-two-newest", "action": {"type": "Keep"},
   "mostRecentVersions": {"keepCount": 2}},
  {"name": "delete-older", "action": {"type": "Delete"},
   "condition": {"tagState": "any", "olderThan": "1d"}}
]
JSON
if gcloud artifacts repositories set-cleanup-policies cloud-run-source-deploy \
     --project "$PROJECT" --location "$REGION" \
     --policy "$POLICY_FILE" --no-dry-run --quiet >/dev/null 2>&1; then
  echo "Old images will be pruned automatically (keeping the newest two)."
else
  echo "Note: could not set an image cleanup policy; old images will accumulate" >&2
  echo "      (a few cents a month at most). The site itself is unaffected." >&2
fi
rm -f "$POLICY_FILE"

echo
echo "Deployed. URL:"
gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --format 'value(status.url)'

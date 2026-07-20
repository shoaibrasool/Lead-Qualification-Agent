#!/bin/bash
set -euo pipefail

# Google Cloud Run deployment script for Lead Qualification Agent
# Prerequisites:
#   1. gcloud CLI installed and authenticated (gcloud auth login)
#   2. A GCP project with billing enabled (free tier is fine)
#   3. Required APIs enabled:
#        gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
#   4. .env file populated with production values (do NOT commit this)
#
# Usage:
#   chmod +x deploy-cloud-run.sh
#   ./deploy-cloud-run.sh

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID or pass it as an env var}"
SERVICE_NAME="${SERVICE_NAME:-lead-agent}"
REGION="${REGION:-us-central1}"

echo "==> Deploying $SERVICE_NAME to Cloud Run in $REGION (project: $PROJECT_ID)"

# Load env vars from .env (skip comments, skip empty lines)
ENV_VARS=$(grep -v '^#' .env | grep -v '^$' | tr '\n' ',' | sed 's/,$//')

if [ -z "$ENV_VARS" ]; then
    echo "ERROR: No env vars found in .env file."
    echo "Copy .env.example to .env and populate it first."
    exit 1
fi

# Deploy from source (auto-builds container via Cloud Build)
gcloud run deploy "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --source . \
    --allow-unauthenticated \
    --cpu-boost \
    --memory=512Mi \
    --timeout=300 \
    --set-env-vars "$ENV_VARS"

echo ""
echo "==> Deployment complete!"
echo "==> Service URL: $(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)')"

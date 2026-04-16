#!/bin/bash

# GCP Cloud Run Deploy Script
# Builds the whatsapp_bot Docker image via Cloud Build and redeploys the
# existing Cloud Run service.
#
# Usage:   ./deploy_gcp.sh [project-id]
# Example: ./deploy_gcp.sh my-gcp-project
#
# If project-id is omitted, the active gcloud project is used.

set -e

# ---------------------------------------------------------------------------
# Config — matches the existing Cloud Run service URL:
#   https://stage-whatsapp-bot-384505539696.us-central1.run.app
# ---------------------------------------------------------------------------
SERVICE_NAME="stage-whatsapp-bot"
IMAGE_NAME="staging-whatsapp-bot"
REGION="us-central1"
SUBDIRECTORY="whatsapp_bot"
BUILD_SERVICE_ACCOUNT="github-deployer-nextclient@tttc-light-js.iam.gserviceaccount.com"

# ---------------------------------------------------------------------------
# Resolve project ID
# ---------------------------------------------------------------------------
if [ -n "$1" ]; then
    PROJECT_ID="$1"
else
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        echo "Error: no GCP project set."
        echo "Either pass a project ID as the first argument or run:"
        echo "  gcloud config set project YOUR_PROJECT_ID"
        exit 1
    fi
fi

IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}"

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: not in a git repository"
    exit 1
fi

if [ ! -d "$SUBDIRECTORY" ]; then
    echo "Error: directory '$SUBDIRECTORY' not found"
    exit 1
fi

echo "============================================"
echo " GCP Cloud Run Deploy"
echo "============================================"
echo " Project : $PROJECT_ID"
echo " Service : $SERVICE_NAME"
echo " Region  : $REGION"
echo " Image   : $IMAGE"
echo " Source  : ./$SUBDIRECTORY"
echo "============================================"
echo ""

read -p "Deploy to Cloud Run? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
echo ""
echo ">>> Building image with Cloud Build..."
gcloud builds submit "$SUBDIRECTORY" \
    --tag "$IMAGE" \
    --service-account="projects/${PROJECT_ID}/serviceAccounts/${BUILD_SERVICE_ACCOUNT}" \
    --default-buckets-behavior=REGIONAL_USER_OWNED_BUCKET \
    --project "$PROJECT_ID"

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------
echo ""
echo ">>> Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE" \
    --region "$REGION" \
    --platform managed \
    --project "$PROJECT_ID"

echo ""
echo "============================================"
echo " Deployment complete!"
echo " https://${SERVICE_NAME}-$(gcloud projects describe "$PROJECT_ID" \
        --format='value(projectNumber)').${REGION}.run.app"
echo "============================================"

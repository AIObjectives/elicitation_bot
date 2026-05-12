#!/bin/bash

# GCP Cloud Run Deploy Script
# Builds the whatsapp_bot Docker image via Cloud Build and redeploys the
# Cloud Run service for the chosen environment.
#
# Usage:
#   ./deploy_gcp.sh --env=staging [--project=PROJECT_ID]
#   ./deploy_gcp.sh --env=prod    [--project=PROJECT_ID]
#
# If --project is omitted, the active gcloud project is used.
#
# Env-specific Twilio credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
# TWILIO_NUMBER) are configured per-service on Cloud Run, not in this script.
# Firebase / Anthropic / OpenAI credentials are shared between environments.

set -e

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
ENV=""
PROJECT_ID=""

for arg in "$@"; do
    case $arg in
        --env=*)     ENV="${arg#*=}" ;;
        --project=*) PROJECT_ID="${arg#*=}" ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Error: unknown argument '$arg'"
            echo "Usage: $0 --env=staging|prod [--project=PROJECT_ID]"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Per-environment config
# ---------------------------------------------------------------------------
case "$ENV" in
    staging)
        SERVICE_NAME="stage-whatsapp-bot"
        IMAGE_NAME="staging-whatsapp-bot"
        ;;
    prod)
        SERVICE_NAME="prod-whatsapp-bot"
        IMAGE_NAME="prod-whatsapp-bot"
        ;;
    "")
        echo "Error: --env is required (staging or prod)"
        echo "Usage: $0 --env=staging|prod [--project=PROJECT_ID]"
        exit 1
        ;;
    *)
        echo "Error: --env must be 'staging' or 'prod' (got '$ENV')"
        exit 1
        ;;
esac

REGION="us-central1"
SUBDIRECTORY="whatsapp_bot"
BUILD_SERVICE_ACCOUNT="github-deployer-nextclient@tttc-light-js.iam.gserviceaccount.com"

# ---------------------------------------------------------------------------
# Resolve project ID
# ---------------------------------------------------------------------------
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        echo "Error: no GCP project set."
        echo "Either pass --project=ID or run:"
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
echo " Env     : $ENV"
echo " Project : $PROJECT_ID"
echo " Service : $SERVICE_NAME"
echo " Region  : $REGION"
echo " Image   : $IMAGE"
echo " Source  : ./$SUBDIRECTORY"
echo "============================================"
echo ""

if [ "$ENV" = "prod" ]; then
    echo "!! You are about to deploy to PRODUCTION."
    read -p "Type 'prod' to confirm: " -r
    echo ""
    if [ "$REPLY" != "prod" ]; then
        echo "Deployment cancelled."
        exit 0
    fi
else
    read -p "Deploy to Cloud Run? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 0
    fi
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

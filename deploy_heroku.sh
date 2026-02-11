#!/bin/bash

# Heroku Deploy Script
# Usage: ./deploy_heroku.sh <remote-name>
# Example: ./deploy_heroku.sh heroku

set -e  # Exit on error

# Check if remote name is provided
if [ -z "$1" ]; then
    echo "Error: Remote name is required"
    echo "Usage: ./deploy_heroku.sh <remote-name>"
    echo "Example: ./deploy_heroku.sh heroku"
    exit 1
fi

REMOTE_NAME="$1"
SUBDIRECTORY="whatsapp_bot"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Check if the subdirectory exists
if [ ! -d "$SUBDIRECTORY" ]; then
    echo "Error: Directory '$SUBDIRECTORY' does not exist"
    exit 1
fi

# Check if the remote exists
if ! git remote get-url "$REMOTE_NAME" > /dev/null 2>&1; then
    echo "Error: Remote '$REMOTE_NAME' does not exist"
    echo "Available remotes:"
    git remote -v
    exit 1
fi

echo "====================================="
echo "Heroku Deploy Script"
echo "====================================="
echo "Remote: $REMOTE_NAME"
echo "Subdirectory: $SUBDIRECTORY"
echo "====================================="
echo ""

# Get the remote URL
REMOTE_URL=$(git remote get-url "$REMOTE_NAME")
echo "Deploying to: $REMOTE_URL"
echo ""

# Confirm force push
read -p "This will FORCE PUSH to $REMOTE_NAME. Continue? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

echo "Force pushing $SUBDIRECTORY to $REMOTE_NAME..."
echo ""

# Use git subtree split to create a branch with only the subdirectory
# then force push that branch to the remote
SPLIT_BRANCH="deploy-$(date +%s)"
echo "Creating temporary split branch: $SPLIT_BRANCH"
git subtree split --prefix "$SUBDIRECTORY" -b "$SPLIT_BRANCH"

echo "Force pushing to $REMOTE_NAME..."
git push "$REMOTE_NAME" "$SPLIT_BRANCH:main" --force

echo "Cleaning up temporary branch..."
git branch -D "$SPLIT_BRANCH"

echo ""
echo "====================================="
echo "Deployment complete!"
echo "====================================="

#!/bin/bash
set -e

# Usage: ./scripts/deploy_frontend.sh <env>
# where <env> is 'dev' or 'prd'

ENV_NAME=${1:-"dev"}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

if [ "$ENV_NAME" != "dev" ] && [ "$ENV_NAME" != "prd" ]; then
  echo "Error: Invalid environment '$ENV_NAME'. Use 'dev' or 'prd'."
  exit 1
fi

export AWS_PROFILE="${AWS_PROFILE:-$ENV_NAME}"

cd "$REPO_ROOT"

echo "Deploying frontend to $ENV_NAME environment..."

# Prefer Compose v2, but keep compatibility with legacy docker-compose.
if command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE_CMD="docker-compose"
else
  DOCKER_COMPOSE_CMD="docker compose"
fi

# Build frontend using Docker to access environment variables
echo "Building frontend..."
$DOCKER_COMPOSE_CMD run --rm --no-deps frontend npm run build

# Get S3 bucket name from Terraform
S3_BUCKET=$(cd terraform && terraform workspace select $ENV_NAME >/dev/null 2>&1 && terraform output -raw s3_bucket_name)

if [ -z "$S3_BUCKET" ]; then
  echo "Error: Could not get S3 bucket name. Run terraform apply first."
  exit 1
fi

echo "Uploading to S3 bucket: $S3_BUCKET"
aws s3 sync frontend/.output/public/ s3://$S3_BUCKET/ --delete

# Clear CloudFront cache
echo "Clearing CloudFront cache..."
DISTRIBUTION_ID=$(cd terraform && terraform workspace select $ENV_NAME >/dev/null 2>&1 && terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"

echo "Frontend deployment complete!"
if [ "$ENV_NAME" = "prd" ]; then
  echo "https://version-check.devtools.site"
else
  echo "https://version-check.dev.devtools.site"
fi

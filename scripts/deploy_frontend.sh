#!/bin/bash
set -e

# Usage: ./scripts/deploy_frontend.sh <env>
# where <env> is 'dev' or 'prd'

ENV_NAME=${1:-"dev"}

if [ "$ENV_NAME" != "dev" ] && [ "$ENV_NAME" != "prd" ]; then
  echo "Error: Invalid environment '$ENV_NAME'. Use 'dev' or 'prd'."
  exit 1
fi

echo "Deploying frontend to $ENV_NAME environment..."

# Build frontend using Docker to access environment variables
echo "Building frontend..."
docker-compose run --rm frontend npm run build

# Get S3 bucket name from Terraform
cd ..
S3_BUCKET=$(cd terraform && terraform workspace select $ENV_NAME >/dev/null 2>&1 && terraform output -raw s3_bucket_name)

if [ -z "$S3_BUCKET" ]; then
  echo "Error: Could not get S3 bucket name. Run terraform apply first."
  exit 1
fi

echo "Uploading to S3 bucket: $S3_BUCKET"
aws s3 sync frontend/.output/public/ s3://$S3_BUCKET/ --delete

# Clear CloudFront cache
echo "Clearing CloudFront cache..."
DISTRIBUTION_ID=$(cd terraform && terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"

echo "Frontend deployment complete!"
echo "https://version-check.devtools.site"

#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-tamafuji-checker}"
REGION="${AWS_REGION:-us-west-2}"

echo "==> Getting stack outputs..."
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)

DIST_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendDistributionId'].OutputValue" \
  --output text)

API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text)

echo "    Bucket:  $BUCKET_NAME"
echo "    Dist ID: $DIST_ID"
echo "    API URL: $API_URL"

echo "==> Building frontend..."
cd "$(dirname "$0")/../frontend"
VITE_API_URL="$API_URL" npm run build

echo "==> Syncing to S3..."
aws s3 sync dist/ "s3://$BUCKET_NAME" --delete --region "$REGION"

echo "==> Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/*" \
  --output text

echo "==> Done! Frontend deployed."
FRONTEND_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" \
  --output text)
echo "    URL: $FRONTEND_URL"

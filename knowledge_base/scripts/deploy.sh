#!/bin/bash
# Deploy RAPTOR Knowledge Base to AWS
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KB_DIR="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$KB_DIR/infra/terraform"

AWS_REGION="${AWS_REGION:-us-west-2}"
AWS_PROFILE="${AWS_PROFILE:-playground}"
# Generate immutable tag from git SHA (can be overridden with IMAGE_TAG env var)
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"

echo "=== RAPTOR Knowledge Base Deployment ==="
echo "Region: $AWS_REGION"
echo "Profile: $AWS_PROFILE"
echo "Image Tag: $IMAGE_TAG"
echo ""

# Step 1: Get ECR repository URL and S3 bucket from Terraform outputs
cd "$TERRAFORM_DIR"

if ! terraform output -json >/dev/null 2>&1; then
    echo "Error: Terraform not initialized or no outputs. Run 'terraform init && terraform apply' first."
    exit 1
fi

ECR_URL=$(terraform output -raw ecr_repository_url)
S3_BUCKET=$(terraform output -raw s3_trees_bucket)
ALB_URL=$(terraform output -raw alb_url)

echo "ECR Repository: $ECR_URL"
echo "S3 Trees Bucket: $S3_BUCKET"
echo "ALB URL: $ALB_URL"
echo ""

# Step 2: Upload tree files to S3
echo "=== Uploading tree files to S3 ==="
cd "$KB_DIR"

if [ -d "trees" ]; then
    echo "Syncing trees/ directory to s3://$S3_BUCKET/trees/"
    aws s3 sync trees/ "s3://$S3_BUCKET/trees/" \
        --profile "$AWS_PROFILE" \
        --exclude "*.html" \
        --exclude "eval/*"
    echo "✓ Tree files uploaded"
else
    echo "Warning: No trees/ directory found. Skipping S3 upload."
fi
echo ""

# Step 3: Build Docker image
echo "=== Building Docker image ==="
cd "$KB_DIR"

# Login to ECR
aws ecr get-login-password --region "$AWS_REGION" --profile "$AWS_PROFILE" | \
    docker login --username AWS --password-stdin "$ECR_URL"

# Build for ARM64 (Graviton) with both SHA tag and :latest for compatibility
docker buildx build \
    --platform linux/arm64 \
    -t "$ECR_URL:$IMAGE_TAG" \
    -t "$ECR_URL:latest" \
    --push \
    .

echo "✓ Image pushed to ECR"
echo ""

# Step 4: Force ECS service update
echo "=== Updating ECS service ==="
ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)
ECS_SERVICE=$(terraform output -raw ecs_service_name)

aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$ECS_SERVICE" \
    --force-new-deployment \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" \
    --no-cli-pager

echo "✓ ECS service update triggered"
echo ""

# Step 5: Output connection info
echo "=== Deployment Complete ==="
echo ""
echo "RAPTOR KB API will be available at:"
echo "  $ALB_URL"
echo ""
echo "Add this to web_ui/.env.local:"
echo "  RAPTOR_API_URL=$ALB_URL"
echo ""
echo "Monitor deployment:"
echo "  aws ecs describe-services --cluster $ECS_CLUSTER --services $ECS_SERVICE --profile $AWS_PROFILE"
echo ""
echo "View logs:"
echo "  aws logs tail /ecs/raptor-kb-production --follow --profile $AWS_PROFILE"

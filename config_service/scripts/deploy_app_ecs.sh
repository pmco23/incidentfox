#!/usr/bin/env bash
set -euo pipefail

# Deploy incidentfox-config-service (API + UI) to AWS as an internal-only endpoint:
# - Terraform creates ECR/ECS/ALB (internal)
# - Builds + pushes Docker image to ECR
# - Updates ECS task definition to the new tag
#
# Usage:
#   AWS_PROFILE=playground AWS_REGION=us-west-2 ./scripts/deploy_app_ecs.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MONO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
TF_DIR="$MONO_ROOT/database/infra/terraform/app"

AWS_PROFILE="${AWS_PROFILE:-playground}"
AWS_REGION="${AWS_REGION:-us-west-2}"

cd "$TF_DIR"

if [ ! -f terraform.tfvars ]; then
  echo "Missing $TF_DIR/terraform.tfvars"
  echo "Run: cp terraform.tfvars.example terraform.tfvars  (and edit if needed)"
  exit 1
fi

echo "Ensuring TOKEN_PEPPER secret exists…"
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" "$ROOT_DIR/scripts/create_token_pepper_secret.sh" >/dev/null

echo "Ensuring ADMIN_TOKEN secret exists…"
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" "$ROOT_DIR/scripts/create_admin_token_secret.sh" >/dev/null

echo "Terraform init/apply (create infra + ECR)…"
terraform init -input=false >/dev/null
terraform apply -auto-approve -var "aws_profile=${AWS_PROFILE}" -var "aws_region=${AWS_REGION}"

ECR_URL="$(terraform output -raw ecr_repository_url)"

IMAGE_TAG="$(date +%Y%m%d%H%M%S)"
IMAGE="${ECR_URL}:${IMAGE_TAG}"

if ! docker info >/dev/null 2>&1; then
  echo ""
  echo "ERROR: Docker daemon is not reachable."
  echo "Start Docker Desktop (or ensure dockerd is running), then re-run:"
  echo "  AWS_PROFILE=${AWS_PROFILE} AWS_REGION=${AWS_REGION} $ROOT_DIR/scripts/deploy_app_ecs.sh"
  echo ""
  echo "To avoid ECS retrying pulls while you fix Docker, scaling service to 0…"
  CLUSTER_NAME="$(terraform output -raw ecs_cluster_name 2>/dev/null || true)"
  SERVICE_NAME="$(terraform output -raw ecs_service_name 2>/dev/null || true)"
  if [ -n "$CLUSTER_NAME" ] && [ -n "$SERVICE_NAME" ]; then
    aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ecs update-service \
      --cluster "$CLUSTER_NAME" \
      --service "$SERVICE_NAME" \
      --desired-count 0 >/dev/null || true
  fi
  exit 1
fi

echo "Logging into ECR…"
# Avoid OS credential helpers (keychain/desktop) which can fail in restricted environments,
# but keep Docker "context" metadata so the CLI can still connect to Docker Desktop.
DOCKER_CONFIG_DIR="${DOCKER_CONFIG_DIR:-$ROOT_DIR/.docker-tmp}"
export DOCKER_CONFIG_DIR
mkdir -p "$DOCKER_CONFIG_DIR"

# Copy contexts so currentContext keeps working (Docker Desktop uses non-default context).
if [ -d "$HOME/.docker/contexts" ]; then
  rm -rf "$DOCKER_CONFIG_DIR/contexts"
  cp -R "$HOME/.docker/contexts" "$DOCKER_CONFIG_DIR/contexts"
fi

# Start from the user's Docker config, but strip credsStore to prevent keychain usage.
if [ -f "$HOME/.docker/config.json" ]; then
  cp "$HOME/.docker/config.json" "$DOCKER_CONFIG_DIR/config.json"
else
  echo '{}' > "$DOCKER_CONFIG_DIR/config.json"
fi

python3 - <<'PY'
import json
from pathlib import Path
import os
p = Path(os.environ["DOCKER_CONFIG_DIR"]) / "config.json"
if not p.exists():
    raise SystemExit(0)
cfg = json.loads(p.read_text() or "{}")
cfg.pop("credsStore", None)
cfg.pop("credHelpers", None)
p.write_text(json.dumps(cfg, indent=2))
PY

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ecr get-login-password | docker --config "$DOCKER_CONFIG_DIR" login --username AWS --password-stdin "${ECR_URL%/*}"

echo "Building image: $IMAGE"
cd "$ROOT_DIR"
docker build -t "$IMAGE" .

echo "Pushing image: $IMAGE"
docker --config "$DOCKER_CONFIG_DIR" push "$IMAGE"

echo "Updating ECS service to image_tag=${IMAGE_TAG}..."
cd "$TF_DIR"
terraform apply -auto-approve -var "aws_profile=${AWS_PROFILE}" -var "aws_region=${AWS_REGION}" -var "image_tag=${IMAGE_TAG}"

ALB_DNS="$(terraform output -raw alb_dns_name)"
echo ""
echo "Deployed."
echo "Internal ALB DNS: ${ALB_DNS}"
echo "To access UI from laptop (no VPN), run:"
echo "  AWS_PROFILE=${AWS_PROFILE} AWS_REGION=${AWS_REGION} ${ROOT_DIR}/scripts/ui_tunnel_aws.sh"



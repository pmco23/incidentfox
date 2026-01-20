#!/usr/bin/env bash
set -euo pipefail

# Start an SSM port-forward tunnel from localhost to the private RDS instance.
#
# Requirements:
# - AWS CLI configured (profile/region)
# - SSM jumpbox deployed (see infra/terraform, output jumpbox_instance_id)
#
# Usage:
#   ./scripts/rds_tunnel.sh
#
# Env vars (optional):
#   AWS_PROFILE (default: playground)
#   AWS_REGION (default: us-west-2)
#   JUMPBOX_INSTANCE_ID (default: derived from terraform output)
#   RDS_HOST (default: derived from terraform output)
#   LOCAL_PORT (default: 5433)

AWS_PROFILE="${AWS_PROFILE:-playground}"
AWS_REGION="${AWS_REGION:-us-west-2}"
LOCAL_PORT="${LOCAL_PORT:-5433}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MONO_ROOT="$(cd "$ROOT/.." && pwd)"

# Allow loading JUMPBOX_INSTANCE_ID from config_service/.env for convenience.
if [[ -z "${JUMPBOX_INSTANCE_ID:-}" && -f "${MONO_ROOT}/config_service/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${MONO_ROOT}/config_service/.env"
  set +a
fi

JUMPBOX_INSTANCE_ID="${JUMPBOX_INSTANCE_ID:-}"
if [[ -z "${JUMPBOX_INSTANCE_ID}" ]]; then
  # Try Terraform output if state exists locally (optional; state is not committed).
  if [[ -d "${ROOT}/infra/terraform/jumpbox" ]]; then
    JUMPBOX_INSTANCE_ID="$(
      cd "${ROOT}/infra/terraform/jumpbox" && terraform output -raw jumpbox_instance_id 2>/dev/null || true
    )"
  fi
fi

sanitize_instance_id () {
  # Accept only actual EC2 instance IDs (e.g. i-0123abcd...). Terraform warnings can leak into stdout.
  local candidate="${1:-}"
  printf '%s\n' "${candidate}" | tr -d '\r' | grep -E '^i-[0-9a-f]{8,}$' || true
}

JUMPBOX_INSTANCE_ID="$(sanitize_instance_id "${JUMPBOX_INSTANCE_ID}")"

if [[ -z "${JUMPBOX_INSTANCE_ID}" || "${JUMPBOX_INSTANCE_ID}" == "None" ]]; then
  # Fallback: discover by Terraform project tag (most robust).
  JUMPBOX_INSTANCE_ID="$(
    aws --profile "${AWS_PROFILE}" --region "${AWS_REGION}" ec2 describe-instances \
      --filters "Name=tag:Project,Values=incidentfox-config-service" "Name=instance-state-name,Values=running" \
      --query "Reservations[0].Instances[0].InstanceId" --output text 2>/dev/null || true
  )"
fi

JUMPBOX_INSTANCE_ID="$(sanitize_instance_id "${JUMPBOX_INSTANCE_ID}")"

if [[ -z "${JUMPBOX_INSTANCE_ID}" || "${JUMPBOX_INSTANCE_ID}" == "None" ]]; then
  # Fallback: discover jumpbox by tag name.
  JUMPBOX_INSTANCE_ID="$(
    aws --profile "${AWS_PROFILE}" --region "${AWS_REGION}" ec2 describe-instances \
      --filters "Name=tag:Name,Values=incidentfox-config-service-jumpbox" "Name=instance-state-name,Values=running" \
      --query "Reservations[0].Instances[0].InstanceId" --output text 2>/dev/null || true
  )"
fi

JUMPBOX_INSTANCE_ID="$(sanitize_instance_id "${JUMPBOX_INSTANCE_ID}")"

if [[ -z "${JUMPBOX_INSTANCE_ID}" || "${JUMPBOX_INSTANCE_ID}" == "None" ]]; then
  echo "Could not determine JUMPBOX_INSTANCE_ID." >&2
  echo "Set it explicitly, e.g.:" >&2
  echo "  AWS_PROFILE=${AWS_PROFILE} AWS_REGION=${AWS_REGION} JUMPBOX_INSTANCE_ID=i-xxxxxxxxxxxxxxxxx ./scripts/rds_tunnel.sh" >&2
  echo "Or ensure your jumpbox EC2 instance is tagged Name=incidentfox-config-service-jumpbox." >&2
  exit 1
fi

# If not provided, derive RDS host from DATABASE_URL in config_service/.env
if [[ -z "${RDS_HOST:-}" && -f "${MONO_ROOT}/config_service/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${MONO_ROOT}/config_service/.env"
  set +a
fi

RDS_HOST="${RDS_HOST:-$(
  python3 - <<'PY'
import os
from urllib.parse import urlparse
u = urlparse(os.environ.get("DATABASE_URL",""))
host = u.hostname or ""
print(host)
PY
)}"

if [[ -z "${RDS_HOST}" ]]; then
  echo "Could not determine RDS host. Set RDS_HOST or ensure DATABASE_URL is set in .env."
  exit 1
fi

echo "Starting SSM port-forward:"
echo "- Jumpbox: ${JUMPBOX_INSTANCE_ID}"
echo "- RDS host: ${RDS_HOST}:5432"
echo "- Local:    127.0.0.1:${LOCAL_PORT}"
echo ""
echo "Press Ctrl+C to stop."

aws --profile "${AWS_PROFILE}" --region "${AWS_REGION}" ssm start-session \
  --target "${JUMPBOX_INSTANCE_ID}" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "host=${RDS_HOST},portNumber=5432,localPortNumber=${LOCAL_PORT}"



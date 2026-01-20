#!/usr/bin/env bash
set -euo pipefail

# Pull the RDS connection info from AWS Secrets Manager and write/update a local .env file.
# This is intended for developer convenience (ad-hoc). Do NOT commit .env.
#
# Requires:
# - aws CLI configured
# - python3 available
#
# Env vars (optional):
#   AWS_PROFILE (default: playground)
#   AWS_REGION  (default: us-west-2)
#   RDS_SECRET_ARN (default: incidentfox-config-service/rds secret)
#   ENV_FILE (default: .env)

AWS_PROFILE="${AWS_PROFILE:-playground}"
AWS_REGION="${AWS_REGION:-us-west-2}"
RDS_SECRET_ARN="${RDS_SECRET_ARN:-arn:aws:secretsmanager:us-west-2:103002841599:secret:incidentfox-config-service/rds}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MONO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$MONO_ROOT/config_service/.env}"

SECRET_JSON="$(aws --profile "${AWS_PROFILE}" --region "${AWS_REGION}" secretsmanager get-secret-value \
  --secret-id "${RDS_SECRET_ARN}" \
  --query SecretString \
  --output text)"

DATABASE_URL="$(SECRET_JSON="${SECRET_JSON}" python3 - <<'PY'
import json, os, urllib.parse
data = json.loads(os.environ["SECRET_JSON"])
user = data["username"]
pw = data["password"]
host = data["host"]
port = data.get("port", 5432)
db = data.get("dbname", "incidentfox_config")
# NOTE: dbname comes from Secrets Manager; fallback below is only for robustness.
if not db:
    db = "incidentfox_config"
# SQLAlchemy URL (psycopg2) + require SSL (RDS parameter forces SSL)
print(f"postgresql+psycopg2://{urllib.parse.quote(user)}:{urllib.parse.quote(pw)}@{host}:{port}/{db}?sslmode=require")
PY
)"

touch "${ENV_FILE}"

upsert () {
  local key="$1"
  local value="$2"
  KEY="${key}" VALUE="${value}" ENV_FILE="${ENV_FILE}" python3 - <<'PY'
import os

env_file = os.environ["ENV_FILE"]
key = os.environ["KEY"]
value = os.environ["VALUE"]

line = f"{key}={value}\n"

try:
    with open(env_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
except FileNotFoundError:
    lines = []

out = []
replaced = False
for existing in lines:
    if existing.startswith(f"{key}="):
        out.append(line)
        replaced = True
    else:
        out.append(existing)

if not replaced:
    if out and not out[-1].endswith("\n"):
        out[-1] = out[-1] + "\n"
    out.append(line)

with open(env_file, "w", encoding="utf-8") as f:
    f.writelines(out)
PY
}

upsert "DATABASE_URL" "${DATABASE_URL}"
upsert "AWS_PROFILE" "${AWS_PROFILE}"
upsert "AWS_REGION" "${AWS_REGION}"
upsert "RDS_SECRET_ARN" "${RDS_SECRET_ARN}"

echo "Wrote DATABASE_URL to ${ENV_FILE}"



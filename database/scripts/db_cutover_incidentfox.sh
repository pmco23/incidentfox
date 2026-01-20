#!/usr/bin/env bash
set -euo pipefail

# Creates an IncidentFox-named database/user on the existing RDS instance (via localhost tunnel),
# copies the existing data from the current DB, and applies migrations.
#
# Preconditions:
# - RDS tunnel running on 127.0.0.1:5433 (see scripts/rds_tunnel.sh)
# - psql + pg_dump installed locally
# - AWS CLI can read the Secrets Manager secret incidentfox-config-service/rds
#
# Usage:
#   AWS_PROFILE=playground AWS_REGION=us-west-2 ./scripts/db_cutover_incidentfox.sh

AWS_PROFILE="${AWS_PROFILE:-playground}"
AWS_REGION="${AWS_REGION:-us-west-2}"

command -v psql >/dev/null

# Ensure tunnel is up
python3 - <<'PY'
import socket, sys
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(("127.0.0.1", 5433))
except Exception:
    print("RDS tunnel not reachable on 127.0.0.1:5433. Start it: ./scripts/rds_tunnel.sh", file=sys.stderr)
    sys.exit(1)
finally:
    try:
        s.close()
    except Exception:
        pass
PY

SECRET_JSON="$(aws --profile "$AWS_PROFILE" --region "$AWS_REGION" secretsmanager get-secret-value \
  --secret-id incidentfox-config-service/rds --query SecretString --output text)"

MASTER_USER="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["username"])' <<<"$SECRET_JSON")"
MASTER_PW="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["password"])' <<<"$SECRET_JSON")"
OLD_DB="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("dbname") or "postgres")' <<<"$SECRET_JSON")"

APP_DB="${APP_DB:-incidentfox_config}"
APP_USER="${APP_USER:-incidentfox}"
APP_PW="${APP_PW:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')}"

export MASTER_USER MASTER_PW OLD_DB APP_DB APP_USER APP_PW

MASTER_URL="$(python3 -c 'import os,urllib.parse; u=urllib.parse.quote(os.environ["MASTER_USER"],safe=""); p=urllib.parse.quote(os.environ["MASTER_PW"],safe=""); d=os.environ["OLD_DB"]; print(f"postgresql://{u}:{p}@127.0.0.1:5433/{d}?sslmode=require")')"
OLD_URL="$(python3 -c 'import os,urllib.parse; u=urllib.parse.quote(os.environ["MASTER_USER"],safe=""); p=urllib.parse.quote(os.environ["MASTER_PW"],safe=""); d=os.environ["OLD_DB"]; print(f"postgresql://{u}:{p}@127.0.0.1:5433/{d}?sslmode=require")')"
NEW_URL="$(python3 -c 'import os,urllib.parse; u=urllib.parse.quote(os.environ["APP_USER"],safe=""); p=urllib.parse.quote(os.environ["APP_PW"],safe=""); d=os.environ["APP_DB"]; print(f"postgresql://{u}:{p}@127.0.0.1:5433/{d}?sslmode=require")')"

echo "Ensuring role+db exist: user=$APP_USER db=$APP_DB"
# Role: create-or-alter
if psql "$MASTER_URL" -v ON_ERROR_STOP=1 -c "CREATE ROLE ${APP_USER} LOGIN PASSWORD '${APP_PW}';" >/dev/null 2>&1; then
  echo "Role created: ${APP_USER}"
else
  psql "$MASTER_URL" -v ON_ERROR_STOP=1 -c "ALTER ROLE ${APP_USER} WITH PASSWORD '${APP_PW}';" >/dev/null
  echo "Role updated: ${APP_USER}"
fi

# DB: create if missing
DB_EXISTS="$(psql "$MASTER_URL" -Atc "select 1 from pg_database where datname='${APP_DB}';" || true)"
if [[ "$DB_EXISTS" != "1" ]]; then
  psql "$MASTER_URL" -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${APP_DB} OWNER ${APP_USER};" >/dev/null
  echo "Database created: ${APP_DB}"
else
  echo "Database exists: ${APP_DB}"
fi

HAS_TABLES="$(psql "$NEW_URL" -Atc "select count(*) from information_schema.tables where table_schema='public';" || echo "0")"
if [[ "$HAS_TABLES" == "0" ]]; then
  echo "Copying data: ${OLD_DB} -> ${APP_DB}"
  DUMP="/tmp/incidentfox_db_dump.sql"

  # pg_dump version must be >= server major version. If local pg_dump is too old,
  # use a Dockerized postgres client (postgres:16) to run pg_dump/psql against the tunnel.
  USE_DOCKER_DUMP=0
  if command -v pg_dump >/dev/null 2>&1; then
    LOCAL_PG_DUMP_MAJOR="$(pg_dump --version | awk '{print $3}' | cut -d. -f1 || echo \"0\")"
    if [[ "$LOCAL_PG_DUMP_MAJOR" -ge 16 ]]; then
      pg_dump --no-owner --no-privileges --format=plain "$OLD_URL" > "$DUMP"
    else
      USE_DOCKER_DUMP=1
    fi
  else
    USE_DOCKER_DUMP=1
  fi

  if [[ "$USE_DOCKER_DUMP" == "1" ]]; then
    command -v docker >/dev/null
    echo "Local pg_dump too old or missing; using docker postgres:16 client tools..."
    docker run --rm \
      -e PGPASSWORD="$MASTER_PW" \
      -e PGSSLMODE=require \
      postgres:16 \
      pg_dump -h host.docker.internal -p 5433 -U "$MASTER_USER" -d "$OLD_DB" --no-owner --no-privileges --format=plain > "$DUMP"
  fi

  # Restore
  if [[ "$USE_DOCKER_DUMP" == "1" ]]; then
    docker run --rm -i \
      -e PGPASSWORD="$APP_PW" \
      -e PGSSLMODE=require \
      postgres:16 \
      psql -h host.docker.internal -p 5433 -U "$APP_USER" -d "$APP_DB" -v ON_ERROR_STOP=1 < "$DUMP" >/dev/null
  else
    psql "$NEW_URL" -v ON_ERROR_STOP=1 < "$DUMP" >/dev/null
  fi
  echo "Restore complete."
else
  echo "Skipping restore; ${APP_DB} already has tables."
fi

export DATABASE_URL_TUNNEL="postgresql+psycopg2://${APP_USER}:${APP_PW}@127.0.0.1:5433/${APP_DB}?sslmode=require"
./scripts/db_migrate.sh

echo ""
echo "OK. Use these values to update the incidentfox-config-service/rds secret:"
echo "  dbname=${APP_DB}"
echo "  username=${APP_USER}"
echo "  password=${APP_PW}"



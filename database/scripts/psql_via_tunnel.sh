#!/usr/bin/env bash
set -euo pipefail

# Connect to the private RDS using an existing localhost tunnel (see rds_tunnel.sh).
#
# Requires:
# - psql installed locally
# - .env contains DATABASE_URL (or set DATABASE_URL)
#
# Usage:
#   ./scripts/psql_via_tunnel.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MONO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"

if [[ -z "${DATABASE_URL:-}" && -f "$MONO_ROOT/config_service/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$MONO_ROOT/config_service/.env"
  set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set. Ensure .env exists (or export DATABASE_URL) and retry."
  exit 1
fi

LOCAL_PORT="${LOCAL_PORT:-5433}"

# Ensure tunnel is up
python3 - <<'PY'
import os, socket, sys
port = int(os.environ.get("LOCAL_PORT","5433"))
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(("127.0.0.1", port))
except Exception:
    print(f"SSM tunnel is not running on 127.0.0.1:{port}.", file=sys.stderr)
    print("Start it in another terminal: ./scripts/rds_tunnel.sh", file=sys.stderr)
    sys.exit(1)
finally:
    try: s.close()
    except Exception: pass
PY

# Rewrite host/port to localhost tunnel, keep creds and db name.
LOCAL_URL="$(python3 - <<'PY'
import os, urllib.parse
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

u = urlparse(os.environ["DATABASE_URL"])
qs = parse_qs(u.query)
# RDS is configured with rds.force_ssl=1, so we must use SSL even via tunnel.
qs["sslmode"] = ["require"]
netloc = u.netloc
# replace host:port (keep user:pass)
if "@" in netloc:
    auth, _host = netloc.split("@", 1)
else:
    auth = ""
new_netloc = f"{auth}@127.0.0.1:{os.environ.get('LOCAL_PORT','5433')}" if auth else f"127.0.0.1:{os.environ.get('LOCAL_PORT','5433')}"
print(urlunparse((u.scheme, new_netloc, u.path, "", urlencode(qs, doseq=True), "")))
PY
)"

echo "Connecting via psql to localhost:${LOCAL_PORT} ..."
psql "${LOCAL_URL/postgresql+psycopg2/postgresql}"



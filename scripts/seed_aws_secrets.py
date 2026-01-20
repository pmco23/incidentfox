#!/usr/bin/env python3
"""
Idempotently seed AWS Secrets Manager for an IncidentFox deployment.

This script is intentionally stdlib-only and shells out to `aws`.

Usage (recommended):
  python scripts/seed_aws_secrets.py --region us-east-1 --from-stdin <<'JSON'
  {
    "incidentfox/pilot/database_url": "postgresql+psycopg://...",
    "incidentfox/pilot/config_service_admin_token": "admin-secret",
    "incidentfox/pilot/config_service_token_pepper": "pepper",
    "incidentfox/pilot/config_service_impersonation_jwt_secret": "jwt-secret",
    "incidentfox/pilot/openai_api_key": "sk-..."
  }
  JSON

Notes:
- Values are written as SecretString.
- If a secret already exists, we only put a new version (safe, idempotent).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


def _run_aws(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise SystemExit(p.stdout.strip())
    return p.stdout.strip()


def _secret_exists(*, name: str, region: str, profile: str | None) -> bool:
    cmd = [
        "aws",
        "secretsmanager",
        "describe-secret",
        "--secret-id",
        name,
        "--region",
        region,
    ]
    if profile:
        cmd += ["--profile", profile]
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.returncode == 0


def _create_secret(*, name: str, value: str, region: str, profile: str | None) -> None:
    cmd = [
        "aws",
        "secretsmanager",
        "create-secret",
        "--name",
        name,
        "--secret-string",
        value,
        "--region",
        region,
    ]
    if profile:
        cmd += ["--profile", profile]
    _run_aws(cmd)


def _put_secret_value(
    *, name: str, value: str, region: str, profile: str | None
) -> None:
    cmd = [
        "aws",
        "secretsmanager",
        "put-secret-value",
        "--secret-id",
        name,
        "--secret-string",
        value,
        "--region",
        region,
    ]
    if profile:
        cmd += ["--profile", profile]
    _run_aws(cmd)


def seed(*, secrets_map: dict[str, str], region: str, profile: str | None) -> None:
    for name, value in secrets_map.items():
        if not isinstance(value, str) or not value:
            raise SystemExit(f"Secret value must be a non-empty string for key: {name}")
        if _secret_exists(name=name, region=region, profile=profile):
            _put_secret_value(name=name, value=value, region=region, profile=profile)
            print(f"updated: {name}")
        else:
            _create_secret(name=name, value=value, region=region, profile=profile)
            print(f"created: {name}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--region", required=True)
    p.add_argument("--profile", default=None)
    p.add_argument("--from-stdin", action="store_true", help="Read JSON map from stdin")
    p.add_argument("--file", default=None, help="Read JSON map from a file")
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    a = _parse_args(argv)
    if bool(a.from_stdin) == bool(a.file is not None):
        raise SystemExit("Provide exactly one of --from-stdin or --file")

    if a.from_stdin:
        raw = sys.stdin.read()
    else:
        raw = open(a.file, "r", encoding="utf-8").read()

    data: Any = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("Expected a JSON object mapping secretName -> secretValue")

    secrets_map: dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(k, str):
            raise SystemExit("Secret names must be strings")
        if not isinstance(v, str):
            raise SystemExit(f"Secret value for {k} must be a string")
        secrets_map[k] = v

    seed(secrets_map=secrets_map, region=a.region, profile=a.profile)


if __name__ == "__main__":
    main(sys.argv[1:])

#!/usr/bin/env python3
"""Seed Extend organization configuration into the config service database.

This script:
1. Creates the 'extend' organization
2. Creates a 'demo' team under extend
3. Loads the extend_org_config.json preset
4. Generates team tokens for testing

Usage:
    python seed_extend_org.py [--config-url URL]
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# Default URLs
DEFAULT_CONFIG_URL = "http://localhost:8090"  # Port-forwarded config service


def load_preset(preset_name: str) -> dict:
    """Load a preset configuration file."""
    presets_dir = Path(__file__).parent.parent / "presets"
    preset_file = presets_dir / f"{preset_name}.json"

    if not preset_file.exists():
        raise FileNotFoundError(f"Preset not found: {preset_file}")

    with open(preset_file) as f:
        return json.load(f)


def create_organization(
    client: httpx.Client, org_id: str, org_name: str, admin_token: str
) -> dict:
    """Create an organization."""
    print(f"Creating organization: {org_id} ({org_name})...")

    resp = client.post(
        "/api/v1/admin/orgs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "org_id": org_id,
            "name": org_name,
            "status": "active",
        },
    )

    if resp.status_code == 409:
        print(f"  Organization '{org_id}' already exists, continuing...")
        return {"org_id": org_id}

    resp.raise_for_status()
    result = resp.json()
    print(f"  Created organization: {result}")
    return result


def create_team(
    client: httpx.Client, org_id: str, team_id: str, team_name: str, admin_token: str
) -> dict:
    """Create a team under an organization."""
    print(f"Creating team: {team_id} ({team_name}) under org {org_id}...")

    resp = client.post(
        f"/api/v1/admin/orgs/{org_id}/nodes",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "node_id": team_id,
            "name": team_name,
            "node_type": "team",
            "parent_id": org_id,
            "status": "active",
        },
    )

    if resp.status_code == 409:
        print(f"  Team '{team_id}' already exists, continuing...")
        return {"node_id": team_id}

    resp.raise_for_status()
    result = resp.json()
    print(f"  Created team: {result}")
    return result


def upsert_config(
    client: httpx.Client, org_id: str, node_id: str, config: dict, admin_token: str
) -> dict:
    """Upsert configuration for a node."""
    print(f"Uploading config to {org_id}/{node_id}...")

    # Remove schema metadata before uploading
    config_clean = {k: v for k, v in config.items() if not k.startswith("$")}

    resp = client.put(
        f"/api/v1/admin/orgs/{org_id}/nodes/{node_id}/config",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        },
        json={"patch": config_clean},
    )

    resp.raise_for_status()
    result = resp.json()
    print("  Config uploaded successfully")
    return result


def generate_team_token(
    client: httpx.Client, org_id: str, team_id: str, admin_token: str
) -> str:
    """Generate a team token for API access."""
    print(f"Generating team token for {org_id}/{team_id}...")

    resp = client.post(
        f"/api/v1/admin/orgs/{org_id}/nodes/{team_id}/tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "description": "Demo token for Extend",
            "expires_in_days": 365,
        },
    )

    resp.raise_for_status()
    result = resp.json()
    token = result.get("token")
    print(f"  Generated token: {token[:20]}..." if token else "  No token returned")
    return token


def main():
    parser = argparse.ArgumentParser(
        description="Seed Extend organization configuration"
    )
    parser.add_argument(
        "--config-url",
        default=os.getenv("CONFIG_BASE_URL", DEFAULT_CONFIG_URL),
        help="Config service URL",
    )
    parser.add_argument(
        "--admin-token",
        default=os.getenv("ADMIN_TOKEN", "admin-token-placeholder"),
        help="Admin API token",
    )
    parser.add_argument(
        "--org-id",
        default="extend",
        help="Organization ID",
    )
    parser.add_argument(
        "--team-id",
        default="demo",
        help="Team ID",
    )

    args = parser.parse_args()

    print("\n=== Seeding Extend Organization ===")
    print(f"Config URL: {args.config_url}")
    print(f"Org ID: {args.org_id}")
    print(f"Team ID: {args.team_id}")
    print()

    # Load preset
    try:
        config = load_preset("extend_org_config")
        print("Loaded extend_org_config.json preset")
        print(f"  Agents: {list(config.get('agents', {}).keys())}")
        print(f"  MCPs: {len(config.get('mcps', {}).get('default', []))} default")
        print()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Connect to config service
    with httpx.Client(base_url=args.config_url, timeout=30.0) as client:
        # Check health
        try:
            health = client.get("/health")
            health.raise_for_status()
            print(f"Config service is healthy: {health.json()}")
            print()
        except Exception as e:
            print(f"ERROR: Could not connect to config service: {e}")
            print(
                "Make sure to run: kubectl port-forward svc/incidentfox-config-service 8090:8080 -n incidentfox"
            )
            sys.exit(1)

        # Create organization
        create_organization(
            client,
            org_id=args.org_id,
            org_name="Extend",
            admin_token=args.admin_token,
        )

        # Create team
        create_team(
            client,
            org_id=args.org_id,
            team_id=args.team_id,
            team_name="Demo Team",
            admin_token=args.admin_token,
        )

        # Upload config to org level
        upsert_config(
            client,
            org_id=args.org_id,
            node_id=args.org_id,  # Org-level config
            config=config,
            admin_token=args.admin_token,
        )

        # Generate team token
        try:
            token = generate_team_token(
                client,
                org_id=args.org_id,
                team_id=args.team_id,
                admin_token=args.admin_token,
            )

            if token:
                print()
                print("=" * 60)
                print("TEAM TOKEN (save this for testing):")
                print(token)
                print("=" * 60)
        except Exception as e:
            print(f"  Warning: Could not generate team token: {e}")

    print()
    print("=== Extend Organization Seeded Successfully ===")
    print()
    print("Next steps:")
    print("1. Configure GitHub App credentials in the Extend org")
    print("2. Set up Coralogix and Snowflake integrations")
    print("3. Point GitHub webhook to: https://your-agent-service/webhooks/github")
    print("4. Test with a failing CI run!")


if __name__ == "__main__":
    main()

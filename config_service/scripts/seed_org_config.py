#!/usr/bin/env python3
"""
Seed Organization Configuration

This script loads a preset configuration into the database for an organization.
It's used to:
1. Initialize new orgs with default config
2. Reset an org to a known good state
3. Test the full config flow

Usage:
    # Using local config service
    python seed_org_config.py --org-id org-1 --preset default
    
    # Using deployed config service
    python seed_org_config.py --org-id org-1 --preset default \
        --api-url http://config-service:8080 \
        --admin-token $ADMIN_TOKEN
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# Presets directory
PRESETS_DIR = Path(__file__).parent.parent / "presets"


def load_preset(preset_name: str) -> dict:
    """Load a preset configuration from file."""
    preset_file = PRESETS_DIR / f"{preset_name}_org_config.json"

    if not preset_file.exists():
        raise FileNotFoundError(f"Preset not found: {preset_file}")

    with open(preset_file) as f:
        config = json.load(f)

    # Remove metadata fields
    config.pop("$schema", None)
    config.pop("$description", None)
    config.pop("$version", None)

    return config


def ensure_org_node_exists(api_url: str, admin_token: str, org_id: str) -> bool:
    """Ensure the org node exists, create if not."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Check if org node exists
    try:
        response = httpx.get(
            f"{api_url}/api/v1/admin/orgs/{org_id}/nodes", headers=headers, timeout=10.0
        )

        if response.status_code == 200:
            nodes = response.json()
            # Check if there's an org-level node
            org_nodes = [n for n in nodes if n.get("node_type") == "org"]
            if org_nodes:
                print(f"✓ Org node exists: {org_nodes[0]['node_id']}")
                return True

        # Create org node
        print(f"Creating org node for {org_id}...")
        response = httpx.post(
            f"{api_url}/api/v1/admin/orgs/{org_id}/nodes",
            headers=headers,
            json={
                "node_id": org_id,
                "node_type": "org",
                "name": f"Organization {org_id}",
                "parent_id": None,
            },
            timeout=10.0,
        )

        if response.status_code in (200, 201):
            print(f"✓ Created org node: {org_id}")
            return True
        else:
            print(f"✗ Failed to create org node: {response.text}")
            return False

    except Exception as e:
        print(f"✗ Error checking/creating org node: {e}")
        return False


def ensure_config_node_exists(
    api_url: str, admin_token: str, org_id: str, node_id: str, node_type: str
) -> bool:
    """Ensure a config node exists in the new config system."""
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    # Try to get the config
    try:
        response = httpx.get(
            f"{api_url}/api/v1/config/orgs/{org_id}/nodes/{node_id}/raw",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            print(f"✓ Config node exists: {node_id}")
            return True

        # Node doesn't exist in config system, we'll create it when we patch
        print(f"Config node {node_id} will be created on first update")
        return True

    except Exception as e:
        print(f"Warning: Could not check config node: {e}")
        return True  # Proceed anyway


def seed_config(
    api_url: str, admin_token: str, org_id: str, node_id: str, config: dict
) -> bool:
    """Seed configuration for a node."""
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    print(f"\nSeeding configuration for {org_id}/{node_id}...")
    print(f"  Agents: {len(config.get('agents', {}))}")
    print(f"  Tools/MCPs: {len(config.get('mcps', {}).get('default', []))}")
    print(f"  Integrations: {len(config.get('integrations', {}))}")

    # Try v2 API first (PATCH), fall back to v1 (PUT)
    endpoints = [
        (f"{api_url}/api/v1/config/orgs/{org_id}/nodes/{node_id}", "PATCH"),
        (f"{api_url}/api/v1/admin/orgs/{org_id}/nodes/{node_id}/config", "PUT"),
    ]

    for endpoint, method in endpoints:
        try:
            print(f"  Trying: {method} {endpoint}")
            if method == "PATCH":
                response = httpx.patch(
                    endpoint,
                    headers=headers,
                    json={"config": config, "merge": False},
                    timeout=30.0,
                )
            else:
                response = httpx.put(
                    endpoint,
                    headers=headers,
                    json={"patch": config},  # v1 API expects {"patch": {...}}
                    timeout=30.0,
                )

            if response.status_code == 200:
                data = response.json()
                print("✓ Configuration seeded successfully!")
                print(f"  Endpoint: {endpoint}")
                return True
            elif response.status_code == 404:
                print("  → 404, trying next endpoint...")
                continue
            else:
                print(f"  → {response.status_code}: {response.text[:200]}")
                continue

        except Exception as e:
            print(f"  → Error: {e}")
            continue

    print("✗ Failed to seed config via any endpoint")
    return False


def verify_config(api_url: str, admin_token: str, org_id: str, node_id: str) -> bool:
    """Verify the configuration was stored correctly."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    print(f"\nVerifying configuration for {org_id}/{node_id}...")

    # Try v2 then v1
    endpoints = [
        (
            f"{api_url}/api/v1/config/orgs/{org_id}/nodes/{node_id}/effective",
            "effective_config",
        ),
        (
            f"{api_url}/api/v1/admin/orgs/{org_id}/nodes/{node_id}/config",
            "config_overrides",
        ),
    ]

    for endpoint, config_key in endpoints:
        try:
            response = httpx.get(endpoint, headers=headers, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                config = data.get(config_key, data)

                agents = config.get("agents", {})
                mcps = config.get("mcps", {}).get("default", [])

                print("✓ Configuration verified:")
                print(f"  Endpoint: {endpoint}")
                print(
                    f"  Agents: {list(agents.keys()) if isinstance(agents, dict) else 'N/A'}"
                )
                print(
                    f"  MCPs: {[m.get('name', m.get('id', '?')) for m in mcps] if isinstance(mcps, list) else 'N/A'}"
                )
                return True

        except Exception:
            continue

    print("✗ Failed to verify config via any endpoint")
    return False


def main():
    parser = argparse.ArgumentParser(description="Seed organization configuration")
    parser.add_argument("--org-id", required=True, help="Organization ID")
    parser.add_argument("--node-id", help="Node ID (defaults to org-id)")
    parser.add_argument(
        "--preset", default="default", help="Preset name (default: default)"
    )
    parser.add_argument(
        "--api-url", default="http://localhost:8090", help="Config service URL"
    )
    parser.add_argument(
        "--admin-token", help="Admin token (or set ADMIN_TOKEN env var)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it",
    )

    args = parser.parse_args()

    # Get admin token
    admin_token = args.admin_token or os.getenv("ADMIN_TOKEN")
    if not admin_token:
        print("Error: Admin token required (--admin-token or ADMIN_TOKEN env var)")
        sys.exit(1)

    node_id = args.node_id or args.org_id

    print("=" * 60)
    print("Seed Organization Configuration")
    print("=" * 60)
    print(f"Org ID: {args.org_id}")
    print(f"Node ID: {node_id}")
    print(f"Preset: {args.preset}")
    print(f"API URL: {args.api_url}")
    print(f"Dry Run: {args.dry_run}")
    print()

    # Load preset
    try:
        config = load_preset(args.preset)
        print(f"✓ Loaded preset: {args.preset}")
    except FileNotFoundError as e:
        print(f"✗ {e}")
        print(
            f"  Available presets: {[f.stem.replace('_org_config', '') for f in PRESETS_DIR.glob('*_org_config.json')]}"
        )
        sys.exit(1)

    if args.dry_run:
        print("\n[DRY RUN] Would seed the following configuration:")
        print(json.dumps(config, indent=2)[:2000] + "...")
        sys.exit(0)

    # Ensure org node exists
    if not ensure_org_node_exists(args.api_url, admin_token, args.org_id):
        sys.exit(1)

    # Seed config
    if not seed_config(args.api_url, admin_token, args.org_id, node_id, config):
        sys.exit(1)

    # Verify
    if not verify_config(args.api_url, admin_token, args.org_id, node_id):
        sys.exit(1)

    print()
    print("=" * 60)
    print("✓ Configuration seeded successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

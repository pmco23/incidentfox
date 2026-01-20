#!/usr/bin/env python3
"""
Migrate preset file from old array-based schema to new dict-based schema.

Converts:
- mcps.default: [...] → mcp_servers: {...}
- agents.*.tools: {enabled: [...], disabled: [...]} → {tool_id: bool}
- agents.*.sub_agents: [...] → {agent_id: bool}
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


def migrate_agent_tools(agent_config: Dict[str, Any]) -> None:
    """Convert agent tools from {enabled: [...], disabled: [...]} to {tool_id: bool}."""
    if "tools" not in agent_config:
        return

    tools_config = agent_config["tools"]
    if not isinstance(tools_config, dict):
        return

    # Old schema: {enabled: [...], disabled: [...]}
    if "enabled" in tools_config or "disabled" in tools_config:
        enabled = tools_config.get("enabled", [])
        disabled = tools_config.get("disabled", [])

        # Convert to new schema: {tool_id: bool}
        new_tools = {}
        for tool_id in enabled:
            new_tools[tool_id] = True
        for tool_id in disabled:
            new_tools[tool_id] = False

        agent_config["tools"] = new_tools


def migrate_agent_sub_agents(agent_config: Dict[str, Any]) -> None:
    """Convert sub_agents from list to dict."""
    if "sub_agents" not in agent_config:
        return

    sub_agents = agent_config["sub_agents"]
    if isinstance(sub_agents, list):
        # Convert to dict with all enabled
        agent_config["sub_agents"] = {agent_id: True for agent_id in sub_agents}


def migrate_mcps_to_mcp_servers(config: Dict[str, Any]) -> None:
    """Convert mcps.default array to mcp_servers dict."""
    if "mcps" not in config:
        return

    mcps_section = config["mcps"]
    if not isinstance(mcps_section, dict):
        return

    # Get MCP list from default array
    mcp_list = mcps_section.get("default", [])
    if not isinstance(mcp_list, list):
        return

    # Convert to dict keyed by ID
    mcp_servers = {}
    for mcp in mcp_list:
        if not isinstance(mcp, dict) or "id" not in mcp:
            continue

        mcp_id = mcp.pop("id")
        mcp_servers[mcp_id] = mcp

    # Replace old mcps section with new mcp_servers
    del config["mcps"]
    config["mcp_servers"] = mcp_servers


def migrate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate entire config from old to new schema."""
    # Migrate agents
    agents = config.get("agents", {})
    for agent_id, agent_config in agents.items():
        if not isinstance(agent_config, dict):
            continue

        migrate_agent_tools(agent_config)
        migrate_agent_sub_agents(agent_config)

        # Ensure mcps field exists
        if "mcps" not in agent_config:
            agent_config["mcps"] = {}

    # Migrate MCPs
    migrate_mcps_to_mcp_servers(config)

    return config


def main():
    preset_dir = Path(__file__).parent.parent / "presets"
    preset_file = preset_dir / "default_org_config.json"

    if not preset_file.exists():
        print(f"ERROR: Preset file not found: {preset_file}")
        sys.exit(1)

    print(f"Migrating preset file: {preset_file}")

    # Load preset
    with open(preset_file) as f:
        config = json.load(f)

    # Check if already migrated
    if "mcp_servers" in config:
        print("✓ Preset already uses new schema (mcp_servers exists)")
        if "mcps" in config:
            print("⚠ Warning: Both 'mcps' and 'mcp_servers' exist - will remove 'mcps'")
    else:
        print("→ Converting from old schema (mcps.default) to new schema (mcp_servers)")

    # Migrate
    config = migrate_config(config)

    # Save backup
    backup_file = preset_file.with_suffix(".json.bak")
    with open(backup_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"✓ Backup saved to: {backup_file}")

    # Save migrated version
    with open(preset_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"✓ Migrated preset saved to: {preset_file}")

    # Summary
    mcp_servers = config.get("mcp_servers", {})
    print("\nMigration complete!")
    print(f"  MCP Servers: {len(mcp_servers)}")
    print(f"  IDs: {list(mcp_servers.keys())}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test script to check MCP configuration."""

# This would normally come from your session token
# For now, let's just check the default config structure

from config_service.src.core.hierarchical_config import get_full_default_config

# Get the defaults
defaults = get_full_default_config(db=None)

print("=" * 80)
print("MCP SERVERS in defaults:")
print("=" * 80)
mcp_servers = defaults.get("mcp_servers", {})
for mcp_id, mcp_config in mcp_servers.items():
    print(f"\nMCP ID: {mcp_id}")
    print(f"Name: {mcp_config.get('name')}")
    print(f"Enabled: {mcp_config.get('enabled')}")
    print(f"Tools: {mcp_config.get('tools', [])}")
    print(f"Enabled Tools: {mcp_config.get('enabled_tools', [])}")

print("\n" + "=" * 80)
print("INTEGRATIONS in defaults:")
print("=" * 80)
integrations = defaults.get("integrations", {})
mcp_integrations = {k: v for k, v in integrations.items() if "mcp" in k.lower()}
for int_id in sorted(mcp_integrations.keys()):
    print(f"\nIntegration ID: {int_id}")

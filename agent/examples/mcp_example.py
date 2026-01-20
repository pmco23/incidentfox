"""
Example: Using MCP Servers with IncidentFox Agent

This example demonstrates how to configure and use MCP servers
with the IncidentFox agent system.

For Serkan's use case (iHeartMedia):
- Shows how to add the EKS MCP server
- Demonstrates tool discovery and usage
- Explains configuration format
"""

import asyncio
import json

from ai_agent.core.mcp_client import (
    cleanup_mcp_connections,
    get_active_mcp_servers,
    get_mcp_tools_for_agent,
    initialize_mcp_servers,
)


async def example_1_filesystem_mcp():
    """
    Example 1: Basic Filesystem MCP Server

    This is the simplest MCP server - provides file system operations.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Filesystem MCP Server")
    print("=" * 70)

    team_config = {
        "team_id": "example-team-1",
        "mcp_servers": [
            {
                "id": "filesystem-mcp",
                "name": "Filesystem MCP",
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                "env": {},
                "enabled": True,
            }
        ],
        "team_added_mcp_servers": [],
        "team_disabled_tool_ids": [],
    }

    try:
        print("\n1. Initializing MCP servers...")
        tools = await initialize_mcp_servers(team_config)

        print("   ✅ Connected to filesystem MCP")
        print(f"   ✅ Discovered {len(tools)} tools")

        print("\n2. Available tools:")
        for tool in tools:
            print(f"   - {tool.__name__}: {tool.__doc__[:60]}...")

        print(f"\n3. Active MCP servers: {get_active_mcp_servers('example-team-1')}")

    finally:
        await cleanup_mcp_connections("example-team-1")
        print("\n✅ Cleanup complete\n")


async def example_2_eks_mcp_for_iheart():
    """
    Example 2: AWS EKS MCP Server (Serkan's Use Case)

    This demonstrates the exact configuration Serkan needs for iHeartMedia.
    The EKS MCP provides 14+ tools for Kubernetes management.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: AWS EKS MCP Server (iHeartMedia Use Case)")
    print("=" * 70)

    team_config = {
        "team_id": "iheart-media",
        "mcp_servers": [
            {
                "id": "eks-mcp",
                "name": "AWS EKS MCP Server",
                "type": "stdio",
                "command": "uvx",
                "args": [
                    "awslabs.eks-mcp-server@latest",
                    "--allow-write",
                    "--allow-sensitive-data-access",
                ],
                "env": {
                    "AWS_REGION": "${aws_region}",
                    "AWS_ACCESS_KEY_ID": "${aws_access_key}",
                    "AWS_SECRET_ACCESS_KEY": "${aws_secret_key}",
                    "FASTMCP_LOG_LEVEL": "ERROR",
                },
                "config_schema": {
                    "aws_region": {
                        "type": "string",
                        "required": True,
                        "display_name": "AWS Region",
                        "description": "AWS region for EKS clusters",
                    },
                    "aws_access_key": {
                        "type": "secret",
                        "required": True,
                        "display_name": "AWS Access Key",
                    },
                    "aws_secret_key": {
                        "type": "secret",
                        "required": True,
                        "display_name": "AWS Secret Key",
                    },
                },
                "config_values": {
                    "aws_region": "us-east-1",
                    "aws_access_key": "AKIA...",  # Actual value from config service
                    "aws_secret_key": "...",  # Actual value from config service
                },
                "enabled": True,
            }
        ],
        "team_added_mcp_servers": [],
        "team_disabled_tool_ids": [],
    }

    print("\nConfiguration Structure:")
    print(json.dumps(team_config["mcp_servers"][0], indent=2, default=str))

    print("\n💡 This configuration would give Serkan's coordinator bot:")
    print("   - manage_eks_stacks (create/delete clusters)")
    print("   - list_k8s_resources (pods, deployments, services)")
    print("   - get_pod_logs (troubleshooting)")
    print("   - get_k8s_events (incident investigation)")
    print("   - apply_yaml (deployment automation)")
    print("   - generate_app_manifest (app deployment)")
    print("   - get_cloudwatch_logs (AWS integration)")
    print("   - search_aws_docs (documentation)")
    print("   ... and 6+ more tools")

    print("\n💡 Total: 14+ tools from ONE config entry\n")


async def example_3_multiple_mcps():
    """
    Example 3: Multiple MCP Servers

    Shows how to configure multiple MCP servers for a comprehensive toolkit.
    This is what a production team configuration might look like.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Multiple MCP Servers (Production Setup)")
    print("=" * 70)

    team_config = {
        "team_id": "production-team",
        "mcp_servers": [
            # GitHub MCP (51 tools)
            {
                "id": "github-mcp",
                "name": "GitHub MCP",
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "${github_token}"},
                "config_values": {"github_token": "ghp_..."},
                "enabled": True,
            },
            # AWS EKS MCP (14 tools)
            {
                "id": "eks-mcp",
                "name": "AWS EKS MCP",
                "type": "stdio",
                "command": "uvx",
                "args": [
                    "awslabs.eks-mcp-server@latest",
                    "--allow-write",
                    "--allow-sensitive-data-access",
                ],
                "env": {
                    "AWS_REGION": "us-east-1",
                    "AWS_ACCESS_KEY_ID": "${aws_key}",
                    "AWS_SECRET_ACCESS_KEY": "${aws_secret}",
                    "FASTMCP_LOG_LEVEL": "ERROR",
                },
                "config_values": {"aws_key": "AKIA...", "aws_secret": "..."},
                "enabled": True,
            },
            # Slack MCP (10 tools)
            {
                "id": "slack-mcp",
                "name": "Slack MCP",
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-slack"],
                "env": {"SLACK_BOT_TOKEN": "${slack_token}"},
                "config_values": {"slack_token": "xoxb-..."},
                "enabled": True,
            },
        ],
        "team_added_mcp_servers": [],
        "team_disabled_tool_ids": [],
    }

    print("\n📦 Configuration Summary:")
    print(f"   - Number of MCP servers: {len(team_config['mcp_servers'])}")
    for mcp in team_config["mcp_servers"]:
        print(f"   - {mcp['name']} ({mcp['id']})")

    print("\n💡 Expected Tool Count:")
    print("   - GitHub MCP: 51 tools")
    print("   - AWS EKS MCP: 14 tools")
    print("   - Slack MCP: 10 tools")
    print("   - Total: 75 tools from 3 config entries")
    print("\n   Plus your 50+ built-in tools = 125+ total tools!\n")


async def example_4_team_inheritance():
    """
    Example 4: Team Inheritance

    Shows how teams inherit org defaults and add their own MCP servers.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Team Inheritance (Org + Team MCPs)")
    print("=" * 70)

    team_config = {
        "team_id": "extend-sre-team",
        # Org-level MCP servers (all teams inherit these)
        "mcp_servers": [
            {
                "id": "github-mcp",
                "name": "GitHub MCP",
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "${github_token}"},
                "source": "org",  # Inherited from org
                "enabled": True,
            }
        ],
        # Team-specific MCP servers (only this team has these)
        "team_added_mcp_servers": [
            {
                "id": "filesystem-mcp",
                "name": "Filesystem MCP",
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/app"],
                "env": {},
                "source": "team",  # Team-added
                "enabled": True,
            }
        ],
        # Team can disable specific tools/MCPs
        "team_disabled_tool_ids": [],
    }

    print("\n📊 Configuration Breakdown:")
    print("\n   Org-level MCPs (inherited by all teams):")
    for mcp in team_config["mcp_servers"]:
        print(f"     - {mcp['name']}")

    print("\n   Team-added MCPs (only for extend-sre-team):")
    for mcp in team_config["team_added_mcp_servers"]:
        print(f"     - {mcp['name']}")

    print("\n💡 Result:")
    print("   - This team gets both org defaults AND team-specific MCPs")
    print("   - Other teams only get the org defaults")
    print("   - Teams can disable org MCPs if needed\n")


async def example_5_using_mcp_tools():
    """
    Example 5: Actually Using MCP Tools

    Shows how to call MCP tools from agent code.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Using MCP Tools in Agent Code")
    print("=" * 70)

    team_config = {
        "team_id": "demo-team",
        "mcp_servers": [
            {
                "id": "filesystem-mcp",
                "name": "Filesystem MCP",
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                "env": {},
                "enabled": True,
            }
        ],
        "team_added_mcp_servers": [],
        "team_disabled_tool_ids": [],
    }

    try:
        print("\n1. Initialize MCP servers...")
        tools = await initialize_mcp_servers(team_config)
        print(f"   ✅ Discovered {len(tools)} tools\n")

        print("2. Get tools for agent...")
        agent_tools = get_mcp_tools_for_agent("demo-team", "planner")
        print(f"   ✅ Retrieved {len(agent_tools)} tools for planner agent\n")

        print("3. Find and call a tool...")
        # Find the list_directory tool
        list_tool = next((t for t in agent_tools if "list" in t.__name__.lower()), None)

        if list_tool:
            print(f"   Calling: {list_tool.__name__}(path='/tmp')")
            result = await list_tool(path="/tmp")
            print(f"   ✅ Result (first 200 chars):\n   {result[:200]}...\n")

        print("4. In agent code, tools are used like normal functions:")
        print("   ```python")
        print("   # Agent automatically has access to MCP tools")
        print("   agent = Agent(")
        print("       name='planner',")
        print(
            "       tools=[...builtin_tools, ...mcp_tools],  # <-- MCP tools added here"
        )
        print("   )")
        print("   ```\n")

    finally:
        await cleanup_mcp_connections("demo-team")


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("MCP Integration Examples for IncidentFox")
    print("=" * 70)
    print("\nThese examples show how to configure and use MCP servers")
    print("in the IncidentFox agent system.\n")

    await example_1_filesystem_mcp()
    await example_2_eks_mcp_for_iheart()
    await example_3_multiple_mcps()
    await example_4_team_inheritance()
    await example_5_using_mcp_tools()

    print("\n" + "=" * 70)
    print("✅ All Examples Complete!")
    print("=" * 70)
    print("\n💡 Next Steps:")
    print("   1. Add MCP servers to team config via Web UI")
    print("   2. Restart agent service to initialize MCP connections")
    print("   3. Tools appear automatically in agent toolkit")
    print("   4. No code changes needed!\n")


if __name__ == "__main__":
    asyncio.run(main())

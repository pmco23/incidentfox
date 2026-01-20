"""
MCP (Model Context Protocol) client integration using official SDK.

This module connects to MCP servers configured in the team config and
dynamically discovers tools that agents can use.

Architecture:
- Uses official `mcp` SDK for protocol communication
- Supports stdio transport (subprocess-based MCP servers)
- Discovers tools at runtime (no hardcoded tool list)
- Integrates seamlessly with existing agent tool system

Usage:
    # At agent startup
    tools = await initialize_mcp_servers(team_config)

    # Get tools for specific agent
    agent_tools = get_mcp_tools_for_agent(team_id, agent_name)

    # At shutdown
    await cleanup_mcp_connections(team_id)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# MCP SDK imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent
from mcp.types import Tool as MCPTool

from .logging import get_logger
from .mcp_loader import (
    MCPServerConfig,
    prepare_mcp_env,
    resolve_mcp_config,
    validate_mcp_config,
)

logger = get_logger(__name__)


@dataclass
class MCPClient:
    """
    Wrapper around an active MCP connection.

    Attributes:
        config: MCP server configuration
        session: Active ClientSession
        tools: List of agent-callable tool functions
        _context_managers: Stack of context managers for cleanup
    """

    config: MCPServerConfig
    session: ClientSession
    tools: list[Callable]
    _context_managers: list[Any]

    async def close(self):
        """Close the MCP connection and cleanup resources."""
        try:
            # Exit context managers in reverse order
            for cm in reversed(self._context_managers):
                try:
                    await cm.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(
                        "mcp_context_exit_error", mcp_id=self.config.id, error=str(e)
                    )

            logger.debug("mcp_client_closed", mcp_id=self.config.id)

        except Exception as e:
            logger.error(
                "mcp_close_error", mcp_id=self.config.id, error=str(e), exc_info=True
            )


async def connect_to_mcp_server(config: MCPServerConfig) -> MCPClient | None:
    """
    Connect to a single MCP server and discover its tools.

    This function:
    1. Validates the MCP server configuration
    2. Starts the MCP server subprocess (stdio transport)
    3. Performs the MCP initialization handshake
    4. Discovers available tools via tools/list
    5. Wraps each MCP tool as an agent-callable function

    Args:
        config: MCP server configuration (from mcp_loader)

    Returns:
        MCPClient with discovered tools, or None if connection fails
    """
    # Validate config first
    validation = validate_mcp_config(config)
    if not validation["valid"]:
        logger.error(
            "mcp_config_invalid",
            mcp_id=config.id,
            missing=validation["missing"],
            errors=validation["errors"],
        )
        return None

    context_managers = []

    try:
        # Prepare environment variables (substitute ${tokens})
        env = prepare_mcp_env(config)

        # Create server parameters for stdio transport
        params = StdioServerParameters(
            command=config.command, args=config.args, env=env
        )

        logger.info(
            "mcp_connecting", mcp_id=config.id, command=config.command, args=config.args
        )

        # Connect via stdio transport
        stdio_ctx = stdio_client(params)
        read, write = await stdio_ctx.__aenter__()
        context_managers.append(stdio_ctx)

        # Create client session
        session_ctx = ClientSession(read, write)
        session = await session_ctx.__aenter__()
        context_managers.append(session_ctx)

        # Perform MCP initialization handshake
        init_result = await session.initialize()

        logger.info(
            "mcp_connected",
            mcp_id=config.id,
            protocol_version=init_result.protocolVersion,
            server_name=(
                init_result.serverInfo.name if init_result.serverInfo else "unknown"
            ),
            has_tools="tools" in str(init_result.capabilities),
            has_resources="resources" in str(init_result.capabilities),
        )

        # Discover tools
        tools_response = await session.list_tools()

        logger.info(
            "mcp_tools_discovered",
            mcp_id=config.id,
            tool_count=len(tools_response.tools),
        )

        # Convert MCP tools to agent-callable functions
        tools = []
        for tool_def in tools_response.tools:
            tool_func = create_agent_tool_from_mcp(
                mcp_id=config.id, tool_def=tool_def, session=session
            )
            tools.append(tool_func)

            logger.debug(
                "mcp_tool_registered",
                mcp_id=config.id,
                tool_name=tool_def.name,
                description=tool_def.description[:100] if tool_def.description else "",
            )

        return MCPClient(
            config=config,
            session=session,
            tools=tools,
            _context_managers=context_managers,
        )

    except Exception as e:
        logger.error(
            "mcp_connection_failed", mcp_id=config.id, error=str(e), exc_info=True
        )

        # Cleanup on failure
        for cm in reversed(context_managers):
            try:
                await cm.__aexit__(None, None, None)
            except:
                pass

        return None


def create_agent_tool_from_mcp(
    mcp_id: str, tool_def: MCPTool, session: ClientSession
) -> Callable:
    """
    Convert an MCP tool definition to an agent-callable function.

    This creates a wrapper function that:
    - Has the same name and description as the MCP tool
    - Accepts kwargs matching the MCP tool's input schema
    - Calls the MCP server via session.call_tool()
    - Returns the result as a string
    - Is decorated with @function_tool for OpenAI Agents SDK compatibility

    Args:
        mcp_id: MCP server ID (for logging and namespacing)
        tool_def: Tool definition from MCP server
        session: Active MCP ClientSession

    Returns:
        Decorated function tool that agents can call
    """
    from agents import Tool

    tool_name = tool_def.name
    tool_description = tool_def.description or f"Tool from {mcp_id} MCP server"
    input_schema = tool_def.inputSchema

    async def mcp_tool_wrapper(**kwargs) -> str:
        """
        Dynamically generated wrapper for MCP tool.

        This function wraps an MCP tool call with error handling
        and response formatting for the agent system.
        """
        try:
            logger.debug(
                "mcp_tool_call_start",
                mcp_id=mcp_id,
                tool_name=tool_name,
                arguments=kwargs,
            )

            # Call tool via MCP protocol
            result = await session.call_tool(tool_name, arguments=kwargs)

            # Extract content from result
            # MCP returns: CallToolResult(content=[TextContent(...), ImageContent(...), ...])
            content_parts = []
            for content in result.content:
                if isinstance(content, TextContent):
                    content_parts.append(content.text)
                elif hasattr(content, "text"):
                    content_parts.append(content.text)
                else:
                    # Handle other content types (images, etc.)
                    content_parts.append(str(content))

            response = "\n\n".join(content_parts)

            logger.debug(
                "mcp_tool_call_success",
                mcp_id=mcp_id,
                tool_name=tool_name,
                response_length=len(response),
            )

            return response

        except Exception as e:
            error_msg = f"Error calling MCP tool '{tool_name}' from {mcp_id}: {str(e)}"
            logger.error(
                "mcp_tool_call_failed",
                mcp_id=mcp_id,
                tool_name=tool_name,
                error=str(e),
                exc_info=True,
            )
            return error_msg

    # Attach metadata for agent system
    # The agent system can inspect these attributes to understand the tool
    tool_wrapper_name = f"{mcp_id}__{tool_name}".replace("-", "_")
    mcp_tool_wrapper.__name__ = tool_wrapper_name
    mcp_tool_wrapper.name = tool_wrapper_name
    mcp_tool_wrapper.__doc__ = tool_description
    mcp_tool_wrapper._mcp_id = mcp_id
    mcp_tool_wrapper._mcp_tool_name = tool_name
    mcp_tool_wrapper._mcp_schema = input_schema
    mcp_tool_wrapper._is_mcp_tool = True

    # Create Tool object manually to bypass strict schema validation
    # MCP tools often have additionalProperties which @function_tool doesn't allow
    try:
        # Use Tool.from_function which is more flexible
        tool = Tool.from_function(
            mcp_tool_wrapper,
            name=tool_wrapper_name,
            description=tool_description,
            strict=False,  # Don't enforce strict schema for MCP tools
        )
        return tool
    except Exception as e:
        # If Tool.from_function doesn't support strict param, just return the function
        # The SDK may accept it anyway
        logger.warning(f"Could not create strict=False Tool, returning function: {e}")
        return mcp_tool_wrapper


# Global registry of active MCP clients per team
_team_mcp_clients: dict[str, list[MCPClient]] = {}


async def initialize_mcp_servers(team_config: dict[str, Any]) -> list[Callable]:
    """
    Initialize MCP connections for a team and return all discovered tools.

    This is called once at agent startup to connect to all configured
    MCP servers and discover their tools.

    Process:
    1. Resolve MCP configuration with inheritance (org + team)
    2. Connect to each MCP server concurrently
    3. Discover tools from each connected server
    4. Return combined list of all tools

    Args:
        team_config: Team's effective configuration (with inheritance resolved)

    Returns:
        List of tool functions from all connected MCP servers
    """
    team_id = team_config.get("team_id", "unknown")

    # Resolve MCP configuration with inheritance
    # This handles: org defaults + team additions - disabled tools
    mcp_configs = resolve_mcp_config(team_config)

    if not mcp_configs:
        logger.info("no_mcp_servers", team_id=team_id)
        return []

    logger.info("mcp_initialization_start", team_id=team_id, mcp_count=len(mcp_configs))

    # Connect to each MCP server concurrently for speed
    connection_tasks = [connect_to_mcp_server(config) for config in mcp_configs]

    clients = await asyncio.gather(*connection_tasks, return_exceptions=True)

    # Filter out failed connections and exceptions
    active_clients = []
    for i, client in enumerate(clients):
        if isinstance(client, MCPClient):
            active_clients.append(client)
        elif isinstance(client, Exception):
            logger.error(
                "mcp_connection_exception",
                team_id=team_id,
                mcp_id=mcp_configs[i].id,
                error=str(client),
            )

    # Store clients for later retrieval and cleanup
    _team_mcp_clients[team_id] = active_clients

    # Collect all tools from all servers
    all_tools = []
    for client in active_clients:
        all_tools.extend(client.tools)

    logger.info(
        "mcp_initialization_complete",
        team_id=team_id,
        connected_servers=len(active_clients),
        failed_servers=len(mcp_configs) - len(active_clients),
        total_tools=len(all_tools),
        mcp_ids=[c.config.id for c in active_clients],
    )

    return all_tools


def get_mcp_tools_for_agent(team_id: str, agent_name: str) -> list[Callable]:
    """
    Get MCP tools available for a specific agent.

    This is called when loading tools for an agent to include
    dynamically discovered MCP tools alongside built-in tools.

    Now supports per-agent tool filtering based on team configuration.

    Args:
        team_id: Team identifier
        agent_name: Agent name (for filtering)

    Returns:
        List of tool functions from MCP servers (filtered for this agent)
    """
    import fnmatch

    clients = _team_mcp_clients.get(team_id, [])

    if not clients:
        logger.debug("no_mcp_clients_for_team", team_id=team_id, agent_name=agent_name)
        return []

    # Collect all tools from all connected MCP servers
    all_tools = []
    for client in clients:
        all_tools.extend(client.tools)

    # Get team config for tool assignments
    from .config import get_config

    config = get_config()

    if not config.team_config:
        logger.debug(
            "no_team_config_all_tools_allowed",
            agent_name=agent_name,
            tool_count=len(all_tools),
        )
        return all_tools  # No restrictions, return all tools

    # Check if there are agent-specific tool assignments
    agent_assignments = getattr(config.team_config, "agent_tool_assignments", {}) or {}
    agent_config = (
        agent_assignments.get(agent_name)
        if isinstance(agent_assignments, dict)
        else None
    )

    if not agent_config:
        logger.debug(
            "no_agent_specific_config_all_tools_allowed",
            agent_name=agent_name,
            tool_count=len(all_tools),
        )
        return all_tools  # No restrictions for this agent

    # Get allowed MCP tool patterns
    allowed_patterns = agent_config.get("mcp_tools", ["*"])

    # If wildcard, return all tools
    if "*" in allowed_patterns:
        logger.debug(
            "agent_gets_all_mcp_tools", agent_name=agent_name, tool_count=len(all_tools)
        )
        return all_tools

    # Filter tools by pattern matching
    filtered_tools = []
    for tool in all_tools:
        tool_name = tool.__name__

        # Check if tool matches any allowed pattern
        for pattern in allowed_patterns:
            if fnmatch.fnmatch(tool_name, pattern):
                filtered_tools.append(tool)
                logger.debug(
                    "mcp_tool_allowed",
                    agent_name=agent_name,
                    tool_name=tool_name,
                    pattern=pattern,
                )
                break  # Tool matched, no need to check other patterns

    logger.info(
        "mcp_tools_filtered_for_agent",
        agent_name=agent_name,
        total_tools=len(all_tools),
        allowed_tools=len(filtered_tools),
        patterns=allowed_patterns,
        filtered_out=len(all_tools) - len(filtered_tools),
    )

    return filtered_tools


async def cleanup_mcp_connections(team_id: str):
    """
    Cleanup MCP connections for a team.

    This should be called when the agent is shutting down to
    properly close MCP server connections and cleanup resources.

    Args:
        team_id: Team identifier
    """
    clients = _team_mcp_clients.pop(team_id, [])

    if not clients:
        logger.debug("no_mcp_connections_to_cleanup", team_id=team_id)
        return

    logger.info("mcp_cleanup_start", team_id=team_id, client_count=len(clients))

    # Close all clients concurrently
    cleanup_tasks = [client.close() for client in clients]
    await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    logger.info("mcp_cleanup_complete", team_id=team_id, closed=len(clients))


def get_active_mcp_servers(team_id: str) -> list[str]:
    """
    Get list of active MCP server IDs for a team.

    Useful for debugging and status reporting.

    Args:
        team_id: Team identifier

    Returns:
        List of MCP server IDs
    """
    clients = _team_mcp_clients.get(team_id, [])
    return [client.config.id for client in clients]


def get_mcp_tool_count(team_id: str) -> int:
    """
    Get total count of MCP tools available for a team.

    Args:
        team_id: Team identifier

    Returns:
        Total number of MCP tools
    """
    clients = _team_mcp_clients.get(team_id, [])
    return sum(len(client.tools) for client in clients)

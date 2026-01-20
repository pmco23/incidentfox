"""
MCP Tool Adapter - Converts MCP tools to OpenAI Agents SDK function_tool format.

This module bridges MCP server tools with the OpenAI Agents SDK.
"""

import json
from collections.abc import Callable
from typing import Any

from agents import function_tool

from ...core.logging import get_logger

logger = get_logger(__name__)


class MCPToolAdapter:
    """
    Adapter that converts MCP tools to OpenAI Agents SDK function_tool format.

    MCP tools have a schema like:
    {
        "name": "grafana_query",
        "description": "Query Grafana metrics",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "PromQL query"}
            },
            "required": ["query"]
        }
    }

    We convert this to an OpenAI function_tool that calls back to the MCP server.
    """

    def __init__(self, mcp_client):
        """
        Initialize adapter with MCP client.

        Args:
            mcp_client: MCPClient instance
        """
        self.mcp_client = mcp_client
        self._tool_cache: dict[str, Callable] = {}

    def convert_mcp_tool(self, server_name: str, tool_def: dict[str, Any]) -> Callable:
        """
        Convert a single MCP tool definition to an OpenAI function_tool.

        Args:
            server_name: Name of the MCP server providing this tool
            tool_def: MCP tool definition dict

        Returns:
            function_tool decorated function
        """
        tool_name = tool_def["name"]
        tool_description = tool_def.get("description", "")
        input_schema = tool_def.get("input_schema", {})

        # Create cache key
        cache_key = f"{server_name}:{tool_name}"

        # Return cached version if exists
        if cache_key in self._tool_cache:
            return self._tool_cache[cache_key]

        # Create wrapper function that calls MCP server
        async def mcp_tool_wrapper(**kwargs) -> str:
            """
            Dynamically generated MCP tool wrapper.

            This function calls the MCP server with the provided arguments.
            """
            try:
                logger.info(
                    "mcp_tool_called",
                    server=server_name,
                    tool=tool_name,
                    args=list(kwargs.keys()),
                )

                result = await self.mcp_client.call_tool(
                    server_name=server_name, tool_name=tool_name, arguments=kwargs
                )

                # Convert result to JSON string for agent consumption
                if isinstance(result, str):
                    return result
                else:
                    return json.dumps(result)

            except Exception as e:
                error_msg = f"MCP tool error: {str(e)}"
                logger.error(
                    "mcp_tool_error",
                    server=server_name,
                    tool=tool_name,
                    error=str(e),
                )
                return json.dumps({"error": error_msg})

        # Set function metadata for OpenAI
        mcp_tool_wrapper.__name__ = tool_name
        mcp_tool_wrapper.__doc__ = (
            tool_description or f"Call {tool_name} on {server_name} MCP server"
        )

        # Convert MCP input schema to Python type hints (best effort)
        # OpenAI Agents SDK will use the docstring and annotations
        self._add_type_annotations(mcp_tool_wrapper, input_schema)

        # Decorate with function_tool
        # Use strict_mode=False because we're dynamically generating this
        wrapped_tool = function_tool(strict_mode=False)(mcp_tool_wrapper)

        # Cache it
        self._tool_cache[cache_key] = wrapped_tool

        logger.debug(
            "mcp_tool_converted",
            server=server_name,
            tool=tool_name,
            params=list(input_schema.get("properties", {}).keys()),
        )

        return wrapped_tool

    def _add_type_annotations(
        self, func: Callable, input_schema: dict[str, Any]
    ) -> None:
        """
        Add parameter annotations to function based on JSON schema.

        This is best-effort - JSON schema types don't perfectly map to Python types.

        Args:
            func: Function to annotate
            input_schema: JSON schema for tool input
        """
        properties = input_schema.get("properties", {})
        required = set(input_schema.get("required", []))

        # Build parameter descriptions for docstring
        param_docs = []
        for param_name, param_schema in properties.items():
            param_type = param_schema.get("type", "any")
            param_desc = param_schema.get("description", "")
            is_required = param_name in required

            param_doc = f"    {param_name}: {param_desc}"
            if is_required:
                param_doc += " (required)"
            param_docs.append(param_doc)

        # Update docstring with parameter information
        if param_docs:
            func.__doc__ = (func.__doc__ or "") + "\n\nArgs:\n" + "\n".join(param_docs)

    def convert_all_tools(
        self, server_name: str, tools: list[dict[str, Any]]
    ) -> list[Callable]:
        """
        Convert all tools from a server.

        Args:
            server_name: Name of the MCP server
            tools: List of MCP tool definitions

        Returns:
            List of function_tool decorated functions
        """
        converted = []
        for tool_def in tools:
            try:
                tool_func = self.convert_mcp_tool(server_name, tool_def)
                converted.append(tool_func)
            except Exception as e:
                logger.error(
                    "tool_conversion_failed",
                    server=server_name,
                    tool=tool_def.get("name", "unknown"),
                    error=str(e),
                )

        logger.info(
            "tools_converted",
            server=server_name,
            total=len(tools),
            converted=len(converted),
        )

        return converted

    def get_all_converted_tools(self) -> dict[str, list[Callable]]:
        """
        Get all tools from all connected MCP servers, converted to function_tool format.

        Returns:
            Dict mapping server name to list of function_tool callables
        """
        import asyncio

        # Get tools from all servers
        all_mcp_tools = asyncio.run(self.mcp_client.get_all_tools())

        # Convert each server's tools
        converted_tools = {}
        for server_name, tools in all_mcp_tools.items():
            converted_tools[server_name] = self.convert_all_tools(server_name, tools)

        total_tools = sum(len(tools) for tools in converted_tools.values())
        logger.info(
            "all_mcp_tools_converted",
            servers=len(converted_tools),
            total_tools=total_tools,
        )

        return converted_tools


# Global adapter instance
_mcp_tool_adapter: MCPToolAdapter | None = None


def get_mcp_tool_adapter(mcp_client=None) -> MCPToolAdapter:
    """
    Get or create the global MCP tool adapter.

    Args:
        mcp_client: Optional MCP client to use (required on first call)

    Returns:
        MCPToolAdapter instance
    """
    global _mcp_tool_adapter

    if _mcp_tool_adapter is None:
        if mcp_client is None:
            from .client import get_mcp_client

            mcp_client = get_mcp_client()
        _mcp_tool_adapter = MCPToolAdapter(mcp_client)

    return _mcp_tool_adapter


def get_mcp_tools_for_agent(agent_name: str) -> list[Callable]:
    """
    Get MCP tools available for a specific agent.

    DEPRECATED: This uses global MCP client which doesn't work in shared-runtime mode.
    Use get_mcp_tools_for_team(team_config) instead.

    Args:
        agent_name: Name of the agent

    Returns:
        List of function_tool callables from MCP servers
    """
    try:
        adapter = get_mcp_tool_adapter()
        all_tools = adapter.get_all_converted_tools()

        # Flatten all tools from all servers
        tools = []
        for server_tools in all_tools.values():
            tools.extend(server_tools)

        logger.info(
            "mcp_tools_loaded_for_agent",
            agent_name=agent_name,
            tool_count=len(tools),
        )

        return tools

    except Exception as e:
        logger.error(
            "failed_to_load_mcp_tools",
            agent_name=agent_name,
            error=str(e),
        )
        return []


def get_mcp_tools_for_team(team_config) -> list[Callable]:
    """
    Get MCP tools for a team's configuration.

    This initializes a team-specific MCP client with their custom MCPs
    and converts all tools to Agent SDK function_tool format.

    Args:
        team_config: TeamLevelConfig object with mcps configuration

    Returns:
        List of function_tool callables
    """
    if not team_config:
        return []

    try:
        import asyncio

        from .client import initialize_mcp_client_from_team_config

        # Check if we're in an event loop already
        try:
            asyncio.get_running_loop()
            logger.warning("cannot_load_mcp_tools_in_running_loop")
            return []
        except RuntimeError:
            pass

        # Initialize MCP client and convert tools
        async def _load_and_convert():
            # Initialize MCP client for this team
            mcp_client = await initialize_mcp_client_from_team_config(team_config)

            if not mcp_client.servers:
                logger.debug("no_mcp_servers_connected_for_team")
                return []

            # Create adapter for this client
            adapter = MCPToolAdapter(mcp_client)

            # Convert all tools
            all_tools_dict = adapter.get_all_converted_tools()

            # Flatten to list
            tools = []
            for server_name, server_tools in all_tools_dict.items():
                tools.extend(server_tools)

            logger.info(
                "mcp_tools_loaded_for_team",
                servers=len(all_tools_dict),
                total_tools=len(tools),
            )

            return tools

        tools = asyncio.run(_load_and_convert())
        return tools

    except Exception as e:
        logger.error(
            "failed_to_load_mcp_tools_for_team",
            error=str(e),
            exc_info=True,
        )
        return []

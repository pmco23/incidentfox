"""
MCP (Model Context Protocol) client.

Connects to MCP servers and fetches available tools/resources.
"""

from abc import abstractmethod
from typing import Any, Protocol

from ...core.logging import get_logger

logger = get_logger(__name__)


class MCPServer(Protocol):
    """Protocol for MCP server implementations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Server name (e.g., 'grafana', 'pagerduty')."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the MCP server.

        Returns:
            True if connected successfully
        """
        ...

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """
        List available tools from this server.

        Returns:
            List of tool definitions
        """
        ...

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a tool on this server.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tool result
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the server."""
        ...


class MCPClient:
    """
    MCP client that manages connections to multiple MCP servers.

    Usage:
        client = MCPClient()
        await client.add_server(GrafanaServer())
        await client.add_server(PagerDutyServer())

        tools = await client.get_all_tools()
        result = await client.call_tool("grafana", "query_metrics", {...})
    """

    def __init__(self):
        """Initialize MCP client."""
        self.servers: dict[str, MCPServer] = {}
        self._health_status: dict[str, dict[str, Any]] = {}
        logger.info("mcp_client_initialized")

    async def add_server(self, server: MCPServer) -> None:
        """
        Add an MCP server.

        Args:
            server: MCP server implementation
        """
        try:
            connected = await server.connect()

            if connected:
                self.servers[server.name] = server
                logger.info("mcp_server_added", server=server.name)
            else:
                logger.warning("mcp_server_connection_failed", server=server.name)

        except Exception as e:
            logger.error("mcp_server_add_error", server=server.name, error=str(e))

    async def get_all_tools(self) -> dict[str, list[dict[str, Any]]]:
        """
        Get all tools from all connected servers.

        Returns:
            Dict mapping server name to list of tools
        """
        all_tools = {}

        for server_name, server in self.servers.items():
            try:
                tools = await server.list_tools()
                all_tools[server_name] = tools
                logger.debug(
                    "mcp_tools_fetched", server=server_name, tool_count=len(tools)
                )
            except Exception as e:
                logger.error("mcp_tools_fetch_error", server=server_name, error=str(e))
                all_tools[server_name] = []

        return all_tools

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """
        Call a tool on a specific server.

        Args:
            server_name: Name of the server
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if server_name not in self.servers:
            raise ValueError(f"Server '{server_name}' not connected")

        server = self.servers[server_name]

        try:
            logger.info("mcp_tool_call", server=server_name, tool=tool_name)
            result = await server.call_tool(tool_name, arguments)
            logger.info("mcp_tool_success", server=server_name, tool=tool_name)
            return result

        except Exception as e:
            logger.error(
                "mcp_tool_error", server=server_name, tool=tool_name, error=str(e)
            )
            raise

    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for server_name, server in self.servers.items():
            try:
                await server.disconnect()
                logger.info("mcp_server_disconnected", server=server_name)
            except Exception as e:
                logger.error("mcp_disconnect_error", server=server_name, error=str(e))

        self.servers.clear()
        self._health_status.clear()

    async def check_server_health(self, server_name: str) -> dict[str, Any]:
        """
        Check health of a specific MCP server.

        Args:
            server_name: Name of the server to check

        Returns:
            Dict with health status information
        """
        if server_name not in self.servers:
            return {
                "server": server_name,
                "healthy": False,
                "error": "Server not found",
                "checked_at": None,
            }

        server = self.servers[server_name]

        try:
            # Try to list tools as a health check
            import time

            start = time.time()
            tools = await server.list_tools()
            duration = time.time() - start

            health_info = {
                "server": server_name,
                "healthy": True,
                "tool_count": len(tools),
                "response_time_ms": round(duration * 1000, 2),
                "checked_at": time.time(),
            }

            self._health_status[server_name] = health_info
            logger.debug(
                "mcp_health_check_success", server=server_name, tools=len(tools)
            )

            return health_info

        except Exception as e:
            health_info = {
                "server": server_name,
                "healthy": False,
                "error": str(e),
                "checked_at": time.time(),
            }

            self._health_status[server_name] = health_info
            logger.warning("mcp_health_check_failed", server=server_name, error=str(e))

            return health_info

    async def check_all_health(self) -> dict[str, dict[str, Any]]:
        """
        Check health of all connected MCP servers.

        Returns:
            Dict mapping server name to health info
        """
        health_results = {}

        for server_name in self.servers.keys():
            health_results[server_name] = await self.check_server_health(server_name)

        healthy_count = sum(1 for h in health_results.values() if h["healthy"])
        logger.info(
            "mcp_health_check_complete",
            total_servers=len(health_results),
            healthy=healthy_count,
            unhealthy=len(health_results) - healthy_count,
        )

        return health_results

    def get_health_status(self) -> dict[str, dict[str, Any]]:
        """
        Get cached health status for all servers.

        Returns:
            Dict mapping server name to last known health info
        """
        return self._health_status.copy()


# Global MCP client
_mcp_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """Get the global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


async def initialize_mcp_client() -> MCPClient:
    """
    Initialize MCP client and connect to configured custom MCP servers.

    DEPRECATED: This function tries to load from global config, which doesn't work
    in shared-runtime mode. Use initialize_mcp_client_from_team_config() instead.
    """
    from ...core.config import get_config

    config = get_config()
    client = get_mcp_client()

    # Check if team has custom MCPs configured
    if not config.team_config:
        logger.info("no_team_config_found_at_startup")
        return client

    # If we have team_config at startup (single-tenant mode), load MCPs
    return await initialize_mcp_client_from_team_config(config.team_config)


async def initialize_mcp_client_from_team_config(team_config) -> MCPClient:
    """
    Initialize MCP client from team config.

    This is called per-request in shared-runtime mode where team_config
    is resolved from the request token.

    Args:
        team_config: TeamLevelConfig object with mcps configuration

    Returns:
        MCPClient with custom MCP servers connected
    """
    from .generic_server import GenericMCPServer

    # Create a new client for this team
    client = MCPClient()

    if not team_config:
        logger.debug("no_team_config_provided")
        return client

    # Load MCP servers from canonical dict format: {mcp_id: {name, command, args, env, ...}}
    mcp_servers = getattr(team_config, "mcp_servers", {})

    if not mcp_servers:
        logger.debug("no_custom_mcps_configured")
        return client

    logger.info("loading_custom_mcp_servers_for_team", count=len(mcp_servers))

    # Initialize MCP servers from dict
    for mcp_id, mcp_config in mcp_servers.items():
        try:
            if not isinstance(mcp_config, dict):
                logger.warning(
                    "invalid_mcp_config_type", mcp_id=mcp_id, type=type(mcp_config)
                )
                continue

            # Skip if explicitly disabled
            if not mcp_config.get("enabled", True):
                logger.debug(
                    "skipping_disabled_mcp", mcp_id=mcp_id, name=mcp_config.get("name")
                )
                continue

            name = mcp_config.get(
                "name", mcp_id
            )  # Fallback to ID if name not specified
            command = mcp_config.get("command")
            args = mcp_config.get("args", [])
            env = mcp_config.get("env", {})

            if not name or not command:
                logger.warning("invalid_mcp_config", config=mcp_config)
                continue

            logger.info(
                "initializing_custom_mcp",
                name=name,
                command=command,
                has_args=len(args) > 0,
                has_env=len(env) > 0,
            )

            server = GenericMCPServer(
                name=name,
                command=command,
                args=args,
                env=env,
            )

            await client.add_server(server)

        except Exception as e:
            logger.error(
                "failed_to_load_custom_mcp",
                name=mcp_config.get("name"),
                error=str(e),
            )

    logger.info(
        "mcp_client_initialized_for_team", connected_servers=len(client.servers)
    )
    return client


async def get_mcp_tools_from_team_config(team_config) -> list[dict[str, Any]]:
    """
    Get all MCP tools available for a team's configuration.

    This initializes a temporary MCP client with the team's custom MCPs
    and returns all available tools.

    Args:
        team_config: TeamLevelConfig object with mcps configuration

    Returns:
        List of tool definitions from all configured MCP servers
    """
    if not team_config:
        return []

    try:
        client = await initialize_mcp_client_from_team_config(team_config)
        all_tools_by_server = await client.get_all_tools()

        # Flatten tools from all servers and add server name as prefix
        all_tools = []
        for server_name, tools in all_tools_by_server.items():
            for tool in tools:
                # Add server name to tool for identification
                tool_with_server = tool.copy()
                tool_with_server["mcp_server"] = server_name
                # Prefix tool name with server name to avoid collisions
                tool_with_server["name"] = f"{server_name}_{tool['name']}"
                all_tools.append(tool_with_server)

        logger.info("mcp_tools_fetched_for_team", total_tools=len(all_tools))
        return all_tools

    except Exception as e:
        logger.error("failed_to_get_mcp_tools_from_team_config", error=str(e))
        return []

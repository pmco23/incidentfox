"""
Tool Pool Management

Provides a centralized registry of all available tools for a team:
- Built-in tools (K8s, AWS, GitHub, Grafana, etc.)
- Custom MCP tools (added by team)

Agents then select from this pool via enable_extra_tools configuration.
"""

import asyncio
from collections.abc import Callable

from ..core.logging import get_logger

logger = get_logger(__name__)


def get_team_tool_pool_with_sources(
    team_config,
) -> tuple[dict[str, Callable], dict[str, str]]:
    """
    Get the complete tool pool with source information.

    Returns:
        Tuple of (tool_pool, tool_sources) where:
        - tool_pool: Dict mapping tool name to tool function
        - tool_sources: Dict mapping tool name to source ('built-in' or 'mcp')
    """
    tool_pool = {}
    tool_sources = {}

    # 1. Load all built-in tools
    built_in_tools = _get_built_in_tools()
    tool_pool.update(built_in_tools)
    for tool_name in built_in_tools:
        tool_sources[tool_name] = "built-in"

    logger.debug("built_in_tools_loaded", count=len(built_in_tools))

    # 2. Load custom MCP tools from team config
    if team_config:
        try:
            mcp_tools = _get_mcp_tools_as_dict(team_config)
            tool_pool.update(mcp_tools)
            for tool_name in mcp_tools:
                tool_sources[tool_name] = "mcp"

            logger.info(
                "team_tool_pool_created",
                built_in_count=len(built_in_tools),
                mcp_count=len(mcp_tools),
                total=len(tool_pool),
            )
        except Exception as e:
            logger.warning("failed_to_load_mcp_tools_for_pool", error=str(e))

    return tool_pool, tool_sources


def get_team_tool_pool(team_config) -> dict[str, Callable]:
    """
    Get the complete tool pool available to a team.

    This includes:
    1. Built-in tools (always available)
    2. Custom MCP tools (from team_config.mcps)

    Returns a dict mapping tool name to tool function.

    Args:
        team_config: TeamLevelConfig object

    Returns:
        Dict mapping tool name to callable tool function

    Example:
        pool = get_team_tool_pool(team_config)
        # pool = {
        #   "k8s_get_pods": <function>,
        #   "github_create_pr": <function>,
        #   "filesystem_read_file": <function from MCP>,
        #   ...
        # }
    """
    tool_pool = {}

    # 1. Load all built-in tools
    built_in_tools = _get_built_in_tools()
    tool_pool.update(built_in_tools)

    logger.debug("built_in_tools_loaded", count=len(built_in_tools))

    # 2. Load custom MCP tools from team config
    if team_config:
        try:
            mcp_tools = _get_mcp_tools_as_dict(team_config)
            tool_pool.update(mcp_tools)

            logger.info(
                "team_tool_pool_created",
                built_in_count=len(built_in_tools),
                mcp_count=len(mcp_tools),
                total=len(tool_pool),
            )
        except Exception as e:
            logger.warning("failed_to_load_mcp_tools_for_pool", error=str(e))

    return tool_pool


def _get_built_in_tools() -> dict[str, Callable]:
    """
    Get all built-in tools as a name-to-function dict.

    This loads tools from tool_loader but returns them as a dict
    for easy lookup by name.
    """
    from .tool_loader import load_tools_for_agent

    # Load all tools (using catalog as agent name since we're getting the full pool)
    all_tools = load_tools_for_agent("catalog")

    # Convert list to dict keyed by tool name
    tool_dict = {}
    for tool in all_tools:
        tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", "unknown")
        tool_dict[tool_name] = tool

    return tool_dict


def _get_mcp_tools_as_dict(team_config) -> dict[str, Callable]:
    """
    Get MCP tools from team config as a name-to-function dict.

    Args:
        team_config: TeamLevelConfig with mcps configuration

    Returns:
        Dict mapping tool name to tool function
    """
    from ..integrations.mcp.tool_adapter import get_mcp_tools_for_team

    # Check if we're in event loop (can't run asyncio.run)
    try:
        asyncio.get_running_loop()
        logger.warning("cannot_load_mcp_tools_in_running_loop")
        return {}
    except RuntimeError:
        pass

    # Get MCP tools as list
    mcp_tools_list = get_mcp_tools_for_team(team_config)

    # Convert to dict keyed by tool name
    tool_dict = {}
    for tool in mcp_tools_list:
        tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", "unknown")
        tool_dict[tool_name] = tool

    return tool_dict


def get_tools_for_agent(
    agent_name: str, default_tools: list, agent_config, team_config
) -> list:
    """
    Get the final tool list for an agent based on configuration.

    This implements the tool selection logic:
    1. Start with default_tools (agent's pre-configured tools)
    2. Remove tools in disable_default_tools
    3. Add tools from enable_extra_tools (from team's tool pool)

    Args:
        agent_name: Name of the agent
        default_tools: Agent's default tool list
        agent_config: AgentConfig object with tool configuration
        team_config: TeamLevelConfig object

    Returns:
        Final list of tools for this agent
    """
    tools = list(default_tools)  # Copy default tools

    # 1. Filter out disabled tools
    if agent_config and agent_config.disable_default_tools:
        original_count = len(tools)
        tools = [
            tool
            for tool in tools
            if getattr(tool, "name", "") not in agent_config.disable_default_tools
        ]
        logger.info(
            "agent_tools_filtered",
            agent_name=agent_name,
            original_count=original_count,
            final_count=len(tools),
            disabled=agent_config.disable_default_tools,
        )

    # 2. Add extra tools from team's tool pool
    if agent_config and agent_config.enable_extra_tools:
        tool_pool = get_team_tool_pool(team_config)

        added_tools = []
        for tool_name in agent_config.enable_extra_tools:
            if tool_name in tool_pool:
                tools.append(tool_pool[tool_name])
                added_tools.append(tool_name)
            else:
                logger.warning(
                    "tool_not_found_in_pool",
                    agent_name=agent_name,
                    tool_name=tool_name,
                    available_tools=list(tool_pool.keys())[:20],  # Sample
                )

        if added_tools:
            logger.info(
                "extra_tools_added_to_agent",
                agent_name=agent_name,
                added_tools=added_tools,
                count=len(added_tools),
            )

    logger.info(
        "agent_tools_finalized",
        agent_name=agent_name,
        total_tools=len(tools),
    )

    return tools

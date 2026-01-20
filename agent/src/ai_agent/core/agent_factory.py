"""
Agent factory that creates agents with team-specific configuration.

Integrates with IncidentFox Config Service to customize:
- Agent prompts
- Available tools
- MCP server integrations
"""

from .config import get_config
from .logging import get_logger

logger = get_logger(__name__)


def create_agent_with_team_config(
    agent_name: str,
    default_create_fn,
    default_prompt: str | None = None,
):
    """
    Create an agent with team-specific configuration from config service.

    Args:
        agent_name: Name of the agent (must match config service agent names)
        default_create_fn: Function that creates the default agent
        default_prompt: Optional override for the default prompt

    Returns:
        Agent configured with team-specific settings

    Example:
        def create_k8s_agent_with_config():
            return create_agent_with_team_config(
                "k8s_agent",
                create_k8s_agent,
                default_prompt="You are a K8s expert..."
            )
    """
    config = get_config()
    team_config = config.team_config

    # Create default agent
    agent = default_create_fn()

    # Apply team-specific configuration if available
    if team_config:
        agent_config = team_config.get_agent_config(agent_name)

        # Check if agent is disabled for this team
        if not agent_config.enabled:
            logger.info("agent_disabled_by_team_config", agent_name=agent_name)
            return None

        # Apply custom prompt if provided
        if agent_config.prompt:
            agent.instructions = agent_config.prompt
            logger.info(
                "agent_custom_prompt_applied",
                agent_name=agent_name,
                prompt_length=len(agent_config.prompt),
            )
        elif default_prompt:
            agent.instructions = default_prompt

        # Apply tool restrictions
        if agent_config.disable_default_tools:
            # Filter out disabled tools
            original_tool_count = len(agent.tools)
            agent.tools = [
                tool
                for tool in agent.tools
                if getattr(tool, "name", "") not in agent_config.disable_default_tools
            ]
            logger.info(
                "agent_tools_filtered",
                agent_name=agent_name,
                original_count=original_tool_count,
                final_count=len(agent.tools),
                disabled=agent_config.disable_default_tools,
            )

        # Add extra tools based on enable_extra_tools
        if agent_config.enable_extra_tools:
            logger.info(
                "extra_tools_requested",
                agent_name=agent_name,
                tools=agent_config.enable_extra_tools,
            )
            # TODO: Implement tool registry for extra built-in tools

        # Load MCP tools if MCP servers are configured
        try:
            from .mcp_client import get_active_mcp_servers, get_mcp_tools_for_agent

            team_id = (
                team_config.team_id if hasattr(team_config, "team_id") else "unknown"
            )
            mcp_tools = get_mcp_tools_for_agent(team_id, agent_name)
            if mcp_tools:
                agent.tools.extend(mcp_tools)
                active_servers = get_active_mcp_servers(team_id)
                logger.info(
                    "mcp_tools_added_to_agent",
                    agent_name=agent_name,
                    mcp_tool_count=len(mcp_tools),
                    mcp_servers=active_servers,
                    total_tools=len(agent.tools),
                )
        except Exception as e:
            logger.warning(
                "failed_to_load_mcp_tools_for_agent",
                agent_name=agent_name,
                error=str(e),
            )

        # Apply timeout if specified
        if agent_config.timeout_seconds:
            # This would need to be passed to AgentRunner
            logger.info(
                "agent_timeout_configured",
                agent_name=agent_name,
                timeout=agent_config.timeout_seconds,
            )

    return agent


def get_enabled_mcp_servers() -> list[str]:
    """
    Get list of enabled MCP servers from team config.

    Returns:
        List of MCP server names (e.g., ["grafana", "pagerduty", "aws"])
    """
    config = get_config()

    if config.team_config:
        mcp_servers = config.team_config.mcp_servers
        logger.info("mcp_servers_loaded", servers=mcp_servers)
        return mcp_servers

    # Default MCP servers if no team config
    return []


def should_enable_tool_for_mcp(tool_name: str, mcp_server: str) -> bool:
    """
    Check if a tool should be enabled based on MCP server config.

    Args:
        tool_name: Name of the tool
        mcp_server: MCP server that provides this tool

    Returns:
        True if the MCP server is enabled for this team

    Example:
        if should_enable_tool_for_mcp("grafana_query", "grafana"):
            tools.append(grafana_query_tool)
    """
    enabled_servers = get_enabled_mcp_servers()
    is_enabled = mcp_server in enabled_servers

    logger.debug(
        "tool_mcp_check",
        tool_name=tool_name,
        mcp_server=mcp_server,
        enabled=is_enabled,
    )

    return is_enabled

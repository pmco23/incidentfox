"""
Planner Agent System Prompt Builder.

This module assembles the complete planner system prompt from 7 layers plus delegation guidance:

1. Core Identity (static) - who you are, role, responsibility
2. Runtime Metadata (injected) - timestamp, org, team, environment
3. Behavioral Foundation (static) - honesty, thoroughness, helpfulness
4. Capabilities (dynamic) - available agents and how to use them
4b. Delegation Guidance (static) - how to effectively delegate to sub-agents
5. Contextual Info (from team config) - service details, dependencies
6. Behavior Overrides (from team config) - team-specific instructions
7. Output Format and Rules (static) - how to structure responses
"""

from datetime import UTC, datetime
from typing import Any

from .agent_capabilities import AGENT_CAPABILITIES, get_enabled_agent_keys
from .layers import (
    LAYER_1_CORE_IDENTITY,
    LAYER_3_BEHAVIORAL_FOUNDATION,
    LAYER_7_OUTPUT_AND_RULES,
    build_behavior_overrides,
    build_capabilities_section,
    build_contextual_info,
    build_delegation_section,
    build_runtime_metadata,
)


def build_planner_system_prompt(
    # Runtime metadata
    org_id: str = "default",
    team_id: str = "default",
    timestamp: str | None = None,
    environment: str | None = None,
    incident_id: str | None = None,
    alert_source: str | None = None,
    # Capabilities
    enabled_agents: list[str] | None = None,
    agent_capabilities: dict[str, dict[str, Any]] | None = None,
    remote_agents: dict[str, dict[str, Any]] | None = None,
    # Team config (for contextual info and behavior overrides)
    team_config: dict[str, Any] | None = None,
) -> str:
    """
    Build the complete planner system prompt.

    This assembles all 7 layers into a complete system prompt:
    1. Core identity (static) - who you are, role, responsibility
    2. Runtime metadata (injected) - timestamp, org, team, environment
    3. Behavioral foundation (static) - honesty, thoroughness, helpfulness
    4. Capabilities (dynamic) - available agents and how to use them
    5. Contextual info (from team config) - service details, dependencies
    6. Behavior overrides (from team config) - team-specific instructions
    7. Output format and rules (static) - how to structure responses

    Args:
        org_id: Organization identifier
        team_id: Team identifier
        timestamp: ISO timestamp (defaults to now if not provided)
        environment: Environment (prod, staging, dev)
        incident_id: Incident/alert ID if applicable
        alert_source: Source of alert (PagerDuty, Datadog, etc.)
        enabled_agents: List of agent keys to include in capabilities
        agent_capabilities: Custom capability descriptors (uses defaults if not provided)
        remote_agents: Dict of remote A2A agent configs
        team_config: Team configuration dict for contextual info and behavior overrides

    Returns:
        Complete system prompt string
    """
    # Defaults
    if timestamp is None:
        timestamp = datetime.now(UTC).isoformat()

    if enabled_agents is None:
        enabled_agents = get_enabled_agent_keys(team_config)

    if agent_capabilities is None:
        agent_capabilities = AGENT_CAPABILITIES

    if team_config is None:
        team_config = {}

    # Build each layer
    layer_1 = LAYER_1_CORE_IDENTITY

    layer_2 = build_runtime_metadata(
        timestamp=timestamp,
        org_id=org_id,
        team_id=team_id,
        environment=environment,
        incident_id=incident_id,
        alert_source=alert_source,
    )

    layer_3 = LAYER_3_BEHAVIORAL_FOUNDATION

    layer_4 = build_capabilities_section(
        enabled_agents=enabled_agents,
        agent_capabilities=agent_capabilities,
        remote_agents=remote_agents,
    )

    # Add delegation guidance for effective sub-agent orchestration
    delegation_guidance = build_delegation_section()

    layer_5 = build_contextual_info(team_config)

    layer_6 = build_behavior_overrides(team_config)

    layer_7 = LAYER_7_OUTPUT_AND_RULES

    # Combine all layers (including delegation guidance after capabilities)
    return (
        layer_1
        + layer_2
        + layer_3
        + layer_4
        + delegation_guidance
        + layer_5
        + layer_6
        + layer_7
    )


def build_planner_system_prompt_from_team_config(
    team_config: Any,
    org_id: str = "default",
    team_id: str = "default",
    environment: str | None = None,
    incident_id: str | None = None,
    alert_source: str | None = None,
    remote_agents: dict[str, dict[str, Any]] | None = None,
) -> str:
    """
    Build planner system prompt from a TeamLevelConfig object.

    This is a convenience wrapper that extracts the relevant fields from
    a TeamLevelConfig object and passes them to build_planner_system_prompt.

    Args:
        team_config: TeamLevelConfig object from config service
        org_id: Organization identifier
        team_id: Team identifier
        environment: Environment (prod, staging, dev)
        incident_id: Incident/alert ID if applicable
        alert_source: Source of alert (PagerDuty, Datadog, etc.)
        remote_agents: Dict of remote A2A agent configs

    Returns:
        Complete system prompt string
    """
    # Extract contextual info from team config
    context_dict = {}

    if team_config:
        # Try to get context fields from team config
        # These might be on the config object directly or in a 'context' sub-dict
        if hasattr(team_config, "context"):
            ctx = team_config.context
            if isinstance(ctx, dict):
                context_dict = ctx
            elif hasattr(ctx, "__dict__"):
                context_dict = {
                    k: v for k, v in ctx.__dict__.items() if not k.startswith("_")
                }
        elif hasattr(team_config, "__dict__"):
            # Look for known context fields directly on config
            for field in [
                "service_info",
                "dependencies",
                "common_issues",
                "common_resources",
                "business_context",
                "known_instability",
                "approval_gates",
                "additional_instructions",
            ]:
                if hasattr(team_config, field):
                    value = getattr(team_config, field)
                    if value:
                        context_dict[field] = value

        # Also check for planner-specific config
        if hasattr(team_config, "get_agent_config"):
            planner_config = team_config.get_agent_config("planner")
            if planner_config:
                # Check for custom additional instructions
                if hasattr(planner_config, "additional_instructions"):
                    instructions = planner_config.additional_instructions
                    if instructions:
                        context_dict["additional_instructions"] = instructions

    return build_planner_system_prompt(
        org_id=org_id,
        team_id=team_id,
        environment=environment,
        incident_id=incident_id,
        alert_source=alert_source,
        remote_agents=remote_agents,
        team_config=context_dict,
    )

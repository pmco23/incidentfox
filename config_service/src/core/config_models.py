"""Configuration models for org/group/team nodes.

Focus is on team-facing fields with arbitrary-depth inheritance across lineage.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TokensVaultPaths(BaseModel):
    openai_token: Optional[str] = None
    slack_bot: Optional[str] = None
    glean: Optional[str] = None


class AgentToggles(BaseModel):
    prompt: str = ""
    enabled: Optional[bool] = None
    disable_default_tools: List[str] = Field(default_factory=list)
    enable_extra_tools: List[str] = Field(default_factory=list)


class AgentsConfig(BaseModel):
    investigation_agent: Optional[AgentToggles] = None
    code_fix_agent: Optional[AgentToggles] = None


class KnowledgeSources(BaseModel):
    grafana: List[str] = Field(default_factory=list)
    google: List[str] = Field(default_factory=list)
    confluence: List[str] = Field(default_factory=list)


class AlertsConfig(BaseModel):
    disabled: List[str] = Field(default_factory=list)


class AIPipelineConfig(BaseModel):
    """Configuration for AI Learning Pipeline.

    Controls whether the AI pipeline is enabled for a team and the schedule
    for pipeline runs that process incident data and build knowledge base.

    Example:
        {
            "enabled": true,
            "schedule": "0 2 * * *"
        }
    """

    enabled: bool = Field(default=False, description="Enable AI pipeline")
    schedule: str = Field(
        default="0 2 * * *",
        description="Cron schedule for pipeline runs (default: 2 AM daily)",
    )


class DependencyDiscoverySourcesConfig(BaseModel):
    """Toggle which discovery sources to use."""

    new_relic: bool = Field(
        default=True, description="Use New Relic distributed tracing"
    )
    cloudwatch: bool = Field(default=False, description="Use AWS X-Ray traces")
    prometheus: bool = Field(
        default=False, description="Use Prometheus service mesh metrics"
    )
    datadog: bool = Field(default=False, description="Use Datadog APM traces")


class DependencyDiscoveryConfig(BaseModel):
    """Configuration for service dependency discovery.

    Controls whether dependency discovery is enabled for a team,
    the schedule for discovery jobs, and which sources to query.

    Example:
        {
            "enabled": true,
            "schedule": "0 */2 * * *",
            "sources": {
                "new_relic": true,
                "datadog": true
            },
            "time_range_hours": 24,
            "min_confidence": 0.7
        }
    """

    enabled: bool = Field(default=False, description="Enable dependency discovery")
    schedule: str = Field(
        default="0 */2 * * *",
        description="Cron schedule for discovery (default: every 2 hours)",
    )
    sources: DependencyDiscoverySourcesConfig = Field(
        default_factory=DependencyDiscoverySourcesConfig,
        description="Which discovery sources to use",
    )
    time_range_hours: int = Field(
        default=24,
        description="How far back to look for dependencies (hours)",
    )
    min_call_count: int = Field(
        default=5,
        description="Minimum calls to consider a valid dependency",
    )
    min_confidence: float = Field(
        default=0.5,
        description="Minimum confidence threshold (0.0 to 1.0)",
    )


class CorrelationConfig(BaseModel):
    """Configuration for alert correlation.

    Controls whether alert correlation is enabled for a team.
    When enabled, incoming alerts are correlated using temporal,
    topology, and semantic analysis to identify related incidents.

    Example:
        {
            "enabled": true,
            "temporal_window_seconds": 300,
            "semantic_threshold": 0.75
        }
    """

    enabled: bool = Field(
        default=False,
        description="Enable alert correlation (feature flag)",
    )
    temporal_window_seconds: int = Field(
        default=300,
        description="Time window in seconds for temporal correlation",
    )
    semantic_threshold: float = Field(
        default=0.75,
        description="Similarity threshold for semantic correlation (0.0 to 1.0)",
    )


class TeamLevelConfig(BaseModel):
    team_name: Optional[str] = None
    tokens_vault_path: Optional[TokensVaultPaths] = None
    mcp_servers: List[str] = Field(default_factory=list)
    a2a_agents: List[str] = Field(default_factory=list)
    slack_group_to_ping: Optional[str] = None
    knowledge_source: Optional[KnowledgeSources] = None
    knowledge_tree: Optional[str] = None
    agents: Optional[AgentsConfig] = None
    alerts: Optional[AlertsConfig] = None
    ai_pipeline: Optional[AIPipelineConfig] = None
    dependency_discovery: Optional[DependencyDiscoveryConfig] = None
    correlation: Optional[CorrelationConfig] = None

    model_config = ConfigDict(extra="allow")


IMMUTABLE_KEYS: List[str] = ["team_name"]


def validate_immutable_fields(
    original: TeamLevelConfig, update: TeamLevelConfig
) -> None:
    """Raise ValueError if an immutable field is present/changed in update.

    For team-scoped writes we currently enforce immutables strictly: clients must not
    set these fields at all (even if original is None).
    """
    for key in IMMUTABLE_KEYS:
        update_value = getattr(update, key, None)
        if update_value is not None:
            raise ValueError(f"Field '{key}' is immutable and cannot be set/changed")

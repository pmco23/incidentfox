"""Base classes and shared utilities for agents."""

from typing import Any

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Base context for all agents."""

    request_id: str
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskContext(AgentContext):
    """Context for task-based agents."""

    task_description: str
    priority: str = "normal"  # low, normal, high, critical
    timeout_seconds: int | None = None

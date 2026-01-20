"""Thinking tool for explicit reasoning."""

from agents import function_tool

from ..core.logging import get_logger

logger = get_logger(__name__)


@function_tool
def think(reasoning: str) -> str:
    """
    Tool for explicit reasoning and analysis.

    Use this when you need to:
    - Think through complex problems
    - Organize information
    - Form hypotheses
    - Plan next steps

    Args:
        reasoning: Your detailed reasoning and analysis

    Returns:
        Confirmation that reasoning was recorded
    """
    logger.info("agent_thinking", reasoning_length=len(reasoning))
    return f"Reasoning recorded ({len(reasoning)} characters). Continue with investigation."

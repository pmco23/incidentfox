"""
Slack update hooks for OpenAI Agents SDK.

Provides real-time Slack updates during agent execution by hooking into
tool calls and agent lifecycle events.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from agents import RunHooks
from agents.run_context import RunContextWrapper
from agents.tool import Tool

from .logging import get_logger

logger = get_logger(__name__)


# Tools grouped by investigation phase
TOOL_TO_PHASE: dict[str, str] = {
    # Snowflake tools -> snowflake_history phase
    "query_snowflake": "snowflake_history",
    "get_snowflake_schema": "snowflake_history",
    "search_incidents_by_service": "snowflake_history",
    "get_recent_incidents": "snowflake_history",
    "get_customer_impact": "snowflake_history",
    "get_deployment_incidents": "snowflake_history",
    # Coralogix logs tools -> coralogix_logs phase
    "search_coralogix_logs": "coralogix_logs",
    "get_coralogix_error_logs": "coralogix_logs",
    "search_coralogix_traces": "coralogix_logs",
    "list_coralogix_services": "coralogix_logs",
    # Coralogix metrics tools -> coralogix_metrics phase
    "query_coralogix_metrics": "coralogix_metrics",
    "get_coralogix_service_health": "coralogix_metrics",
    "get_coralogix_alerts": "coralogix_metrics",
    # Kubernetes tools -> kubernetes phase
    "list_pods": "kubernetes",
    "get_pod_logs": "kubernetes",
    "get_pod_events": "kubernetes",
    "describe_pod": "kubernetes",
    "describe_deployment": "kubernetes",
    "get_pod_resource_usage": "kubernetes",
}


@dataclass
class PhaseUpdate:
    """Represents an update for an investigation phase."""

    phase: str
    status: str  # 'running', 'done', 'failed'
    tool_name: str
    summary: str | None = None
    duration_seconds: float | None = None


@dataclass
class SlackUpdateState:
    """Tracks state for Slack updates during an investigation."""

    channel_id: str
    message_ts: str
    thread_ts: str | None = None

    # Phase status tracking
    phase_status: dict[str, str] = field(default_factory=dict)
    phase_results: dict[str, str] = field(default_factory=dict)

    # Tool call tracking (for batching)
    pending_tool_updates: list[PhaseUpdate] = field(default_factory=list)
    tool_start_times: dict[str, float] = field(default_factory=dict)

    # Debounce tracking
    last_update_time: float = 0
    update_debounce_seconds: float = 2.0  # Min time between Slack updates

    # Investigation metadata
    incident_id: str | None = None
    severity: str | None = None
    title: str = "IncidentFox Investigation"


class SlackUpdateHooks(RunHooks):
    """
    RunHooks implementation that sends real-time updates to Slack.

    Key features:
    - Groups tool calls by investigation phase
    - Debounces updates to avoid spamming Slack
    - Provides meaningful status updates without overwhelming detail
    """

    def __init__(
        self,
        state: SlackUpdateState,
        slack_client: Any,
        on_phase_complete: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        """
        Initialize Slack update hooks.

        Args:
            state: SlackUpdateState with channel/message info
            slack_client: Slack WebClient for posting updates
            on_phase_complete: Optional callback when a phase completes
        """
        self.state = state
        self.slack_client = slack_client
        self.on_phase_complete = on_phase_complete
        self._update_lock = asyncio.Lock()
        self._pending_update_task: asyncio.Task | None = None

    async def on_tool_start(
        self,
        context: RunContextWrapper,
        agent: Any,
        tool: Tool,
    ) -> None:
        """Called when a tool is about to run."""
        try:
            tool_name = getattr(tool, "name", str(tool))
            phase = TOOL_TO_PHASE.get(tool_name)

            if not phase:
                # Tool not mapped to a phase, skip
                return

            self.state.tool_start_times[tool_name] = time.time()

            # Mark phase as running if not already
            if self.state.phase_status.get(phase) != "done":
                old_status = self.state.phase_status.get(phase)
                if old_status != "running":
                    self.state.phase_status[phase] = "running"
                    await self._schedule_update()

            logger.debug("slack_hook_tool_start", tool=tool_name, phase=phase)

        except Exception as e:
            logger.warning("slack_hook_error", error=str(e), event="on_tool_start")

    async def on_tool_end(
        self,
        context: RunContextWrapper,
        agent: Any,
        tool: Tool,
        result: str,
    ) -> None:
        """Called when a tool finishes."""
        try:
            tool_name = getattr(tool, "name", str(tool))
            phase = TOOL_TO_PHASE.get(tool_name)

            if not phase:
                return

            # Calculate duration
            start_time = self.state.tool_start_times.pop(tool_name, None)
            duration = time.time() - start_time if start_time else None

            # Extract a brief summary from the result
            summary = self._extract_summary(tool_name, result)

            # Queue the update
            update = PhaseUpdate(
                phase=phase,
                status="done",
                tool_name=tool_name,
                summary=summary,
                duration_seconds=duration,
            )
            self.state.pending_tool_updates.append(update)

            # Store phase result
            if phase not in self.state.phase_results:
                self.state.phase_results[phase] = ""
            self.state.phase_results[phase] += f"\n\n**{tool_name}:**\n{result[:1000]}"

            logger.debug(
                "slack_hook_tool_end", tool=tool_name, phase=phase, duration=duration
            )

            await self._schedule_update()

        except Exception as e:
            logger.warning("slack_hook_error", error=str(e), event="on_tool_end")

    def _extract_summary(self, tool_name: str, result: str) -> str | None:
        """Extract a one-line summary from tool result."""
        if not result:
            return None

        # Truncate and clean up
        result = result.strip()

        # Try to extract key info based on tool type
        if "error" in tool_name.lower():
            # Count errors
            error_count = result.lower().count("error")
            if error_count > 0:
                return f"Found {error_count} error(s)"

        if "incidents" in tool_name.lower() or "history" in tool_name.lower():
            # Try to count incidents
            import re

            matches = re.findall(r"(\d+)\s+incident", result.lower())
            if matches:
                return f"Found {matches[0]} related incident(s)"

        # Default: first line, truncated
        first_line = result.split("\n")[0][:80]
        return first_line if len(first_line) > 10 else None

    async def _schedule_update(self) -> None:
        """Schedule a debounced Slack update."""
        async with self._update_lock:
            now = time.time()
            time_since_last = now - self.state.last_update_time

            if time_since_last >= self.state.update_debounce_seconds:
                # Update immediately
                await self._send_update()
            elif self._pending_update_task is None or self._pending_update_task.done():
                # Schedule delayed update
                delay = self.state.update_debounce_seconds - time_since_last
                self._pending_update_task = asyncio.create_task(
                    self._delayed_update(delay)
                )

    async def _delayed_update(self, delay: float) -> None:
        """Wait then send update."""
        await asyncio.sleep(delay)
        async with self._update_lock:
            await self._send_update()

    async def _send_update(self) -> None:
        """Send the actual Slack update."""
        try:
            from ..integrations.slack_ui import build_investigation_dashboard

            # Determine which phases are complete
            # A phase is "done" if we've received tool results from it
            # and there are no more tools running in that phase
            running_tools_by_phase: dict[str, int] = {}
            for tool_name in self.state.tool_start_times:
                phase = TOOL_TO_PHASE.get(tool_name)
                if phase:
                    running_tools_by_phase[phase] = (
                        running_tools_by_phase.get(phase, 0) + 1
                    )

            for update in self.state.pending_tool_updates:
                # If no more tools running in this phase and we have results, mark done
                if running_tools_by_phase.get(update.phase, 0) == 0:
                    if update.phase in self.state.phase_results:
                        self.state.phase_status[update.phase] = "done"
                        if self.on_phase_complete:
                            await self.on_phase_complete(
                                update.phase, self.state.phase_results[update.phase]
                            )

            self.state.pending_tool_updates.clear()

            # Build and send dashboard
            blocks = build_investigation_dashboard(
                phase_status=self.state.phase_status,
                title=self.state.title,
                incident_id=self.state.incident_id,
                severity=self.state.severity,
            )

            await self.slack_client.chat_update(
                channel=self.state.channel_id,
                ts=self.state.message_ts,
                text="Investigation in progress...",
                blocks=blocks,
            )

            self.state.last_update_time = time.time()
            logger.debug("slack_update_sent", phases=self.state.phase_status)

        except Exception as e:
            logger.error("slack_update_failed", error=str(e))

    async def finalize(
        self,
        findings: str | None = None,
        confidence: int | None = None,
    ) -> None:
        """
        Finalize the investigation and send the final update.

        Args:
            findings: Root cause analysis findings
            confidence: Confidence score 0-100
        """
        try:
            from ..integrations.slack_ui import build_investigation_dashboard

            # Mark all in-progress phases as done
            for phase in self.state.phase_status:
                if self.state.phase_status[phase] == "running":
                    self.state.phase_status[phase] = "done"

            # Mark RCA phase
            self.state.phase_status["root_cause_analysis"] = "done"

            # Build final dashboard
            blocks = build_investigation_dashboard(
                phase_status=self.state.phase_status,
                title=self.state.title,
                incident_id=self.state.incident_id,
                severity=self.state.severity,
                findings=findings,
                confidence=confidence,
                show_actions=True,
            )

            await self.slack_client.chat_update(
                channel=self.state.channel_id,
                ts=self.state.message_ts,
                text="Investigation complete",
                blocks=blocks,
            )

            logger.info(
                "slack_investigation_finalized", incident_id=self.state.incident_id
            )

        except Exception as e:
            logger.error("slack_finalize_failed", error=str(e))

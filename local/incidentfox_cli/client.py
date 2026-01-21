"""HTTP client for IncidentFox Agent API."""

import json
from typing import Any, AsyncGenerator, Dict, List

import httpx


class AgentClient:
    """Client for IncidentFox Agent API."""

    def __init__(self, base_url: str, team_token: str):
        """
        Initialize agent client.

        Args:
            base_url: Agent service URL (e.g., http://localhost:8081)
            team_token: Team authentication token
        """
        self.base_url = base_url.rstrip("/")
        self.team_token = team_token
        self.timeout = httpx.Timeout(600.0)  # 10 minute timeout for investigations

    def _headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.team_token}",
            "Content-Type": "application/json",
            "X-IncidentFox-Team-Token": self.team_token,
        }

    def check_health(self) -> bool:
        """
        Check if agent service is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    def list_agents(self) -> List[str]:
        """
        List available agents.

        Returns:
            List of agent names
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.base_url}/agents", headers=self._headers())
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("agents", [])
        except Exception:
            pass

        # Fallback to known agents if API doesn't support listing
        return [
            "planner",
            "investigation_agent",
            "k8s_agent",
            "aws_agent",
            "metrics_agent",
            "coding_agent",
            "ci_agent",
        ]

    async def run_agent(self, agent_name: str, message: str) -> Dict[str, Any]:
        """
        Run an agent with a message.

        Args:
            agent_name: Name of agent to run (e.g., "planner")
            message: User message/query

        Returns:
            Dict with success, output/error, duration, agent
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/agents/{agent_name}/run",
                    headers=self._headers(),
                    json={
                        "message": message,
                        "context": {},
                        "max_turns": 20,
                        "timeout": 600,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json()
                    # Handle different response formats
                    output = (
                        data.get("output")
                        or data.get("final_output")
                        or data.get("result", {}).get("output")
                        or data.get("result", {}).get("final_output")
                        or "Investigation complete."
                    )
                    return {
                        "success": True,
                        "output": output,
                        "duration": data.get("duration_seconds")
                        or data.get("duration"),
                        "agent": agent_name,
                        "tool_calls": data.get("tool_calls_count"),
                    }
                else:
                    error_detail = resp.text[:500]
                    try:
                        error_json = resp.json()
                        error_detail = error_json.get("detail", error_detail)
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "error": f"HTTP {resp.status_code}: {error_detail}",
                        "agent": agent_name,
                    }

            except httpx.TimeoutException:
                return {
                    "success": False,
                    "error": "Investigation timed out after 10 minutes",
                    "agent": agent_name,
                }
            except httpx.ConnectError:
                return {
                    "success": False,
                    "error": f"Cannot connect to agent at {self.base_url}",
                    "agent": agent_name,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "agent": agent_name,
                }

    async def run_agent_stream(
        self, agent_name: str, message: str, previous_response_id: str | None = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run an agent with SSE streaming.

        Yields events as the agent executes:
        - agent_started: Agent execution has begun
        - tool_started: A tool call is starting
        - tool_completed: A tool call has finished
        - agent_completed: Final result (includes success, output, duration, last_response_id)

        Args:
            agent_name: Name of agent to run (e.g., "planner")
            message: User message/query
            previous_response_id: Optional response ID for chaining (continues conversation without pre-creating)

        Yields:
            Dict with event_type and event data
        """
        url = f"{self.base_url}/agents/{agent_name}/run/stream"

        # Build request body
        request_body = {
            "message": message,
            "context": {},
            "max_turns": 20,
            "timeout": 600,
        }
        # Include previous_response_id if provided (for chaining follow-up queries)
        if previous_response_id:
            request_body["previous_response_id"] = previous_response_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    url,
                    headers=self._headers(),
                    json=request_body,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield {
                            "event_type": "error",
                            "error": f"HTTP {response.status_code}: {error_text.decode()[:500]}",
                        }
                        return

                    # Parse SSE events
                    event_type = None
                    data_buffer = []

                    async for line in response.aiter_lines():
                        line = line.strip()

                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            data_buffer.append(line[5:].strip())
                        elif line == "" and event_type and data_buffer:
                            # End of event - parse and yield
                            try:
                                data_str = "".join(data_buffer)
                                data = json.loads(data_str)
                                yield {
                                    "event_type": event_type,
                                    **data,
                                }
                            except json.JSONDecodeError:
                                yield {
                                    "event_type": event_type,
                                    "raw_data": "".join(data_buffer),
                                }
                            # Reset for next event
                            event_type = None
                            data_buffer = []

            except httpx.TimeoutException:
                yield {
                    "event_type": "error",
                    "error": "Connection timed out",
                }
            except httpx.ConnectError:
                yield {
                    "event_type": "error",
                    "error": f"Cannot connect to agent at {self.base_url}",
                }
            except Exception as e:
                yield {
                    "event_type": "error",
                    "error": str(e),
                }

    def get_config(self) -> Dict[str, Any]:
        """
        Get current team configuration.

        Returns:
            Team configuration dict
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{self.base_url}/api/v1/config", headers=self._headers()
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return {}

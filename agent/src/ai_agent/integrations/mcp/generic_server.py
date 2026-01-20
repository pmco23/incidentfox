"""
Generic MCP server adapter for custom user-provided MCP servers.

Executes external MCP servers via command/args and communicates via stdio
using the Model Context Protocol (JSON-RPC 2.0).
"""

import asyncio
import json
import os
from typing import Any

from ...core.logging import get_logger

logger = get_logger(__name__)


class GenericMCPServer:
    """
    Generic MCP server that executes external commands and communicates via stdio.

    Implements the MCP (Model Context Protocol) client interface for connecting
    to user-provided MCP servers.
    """

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ):
        """
        Initialize a generic MCP server.

        Args:
            name: Display name for this server
            command: Executable command (e.g., "npx", "python", "/path/to/binary")
            args: List of command arguments
            env: Environment variables to set
        """
        self._name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.connected = False
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._tools_cache: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    async def connect(self) -> bool:
        """Start the MCP server process and initialize connection."""
        try:
            # Prepare environment
            full_env = os.environ.copy()
            full_env.update(self.env)

            # Start subprocess
            logger.info(
                "starting_mcp_server",
                name=self.name,
                command=self.command,
                args=self.args,
            )

            self.process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
            )

            # Send initialize request
            init_response = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "incidentfox-agent", "version": "1.0.0"},
                },
            )

            if init_response.get("error"):
                logger.error(
                    "mcp_init_failed",
                    name=self.name,
                    error=init_response["error"],
                )
                return False

            # Send initialized notification
            await self._send_notification("notifications/initialized")

            self.connected = True
            logger.info("mcp_server_connected", name=self.name)
            return True

        except Exception as e:
            logger.error("mcp_connect_error", name=self.name, error=str(e))
            return False

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the MCP server."""
        if not self.connected:
            raise RuntimeError(f"MCP server '{self.name}' not connected")

        try:
            response = await self._send_request("tools/list", {})

            if response.get("error"):
                logger.error(
                    "mcp_list_tools_failed",
                    name=self.name,
                    error=response["error"],
                )
                return []

            tools = response.get("result", {}).get("tools", [])

            # Transform to our expected format
            formatted_tools = []
            for tool in tools:
                formatted_tools.append(
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "input_schema": tool.get("inputSchema", {}),
                    }
                )

            self._tools_cache = formatted_tools
            logger.debug(
                "mcp_tools_listed",
                name=self.name,
                tool_count=len(formatted_tools),
            )

            return formatted_tools

        except Exception as e:
            logger.error("mcp_list_tools_error", name=self.name, error=str(e))
            return []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        if not self.connected:
            raise RuntimeError(f"MCP server '{self.name}' not connected")

        try:
            logger.info("mcp_calling_tool", name=self.name, tool=tool_name)

            response = await self._send_request(
                "tools/call",
                {
                    "name": tool_name,
                    "arguments": arguments,
                },
            )

            if response.get("error"):
                error_msg = response["error"].get("message", "Unknown error")
                logger.error(
                    "mcp_tool_call_failed",
                    name=self.name,
                    tool=tool_name,
                    error=error_msg,
                )
                return {"error": error_msg}

            result = response.get("result", {})
            logger.info("mcp_tool_call_success", name=self.name, tool=tool_name)

            # Extract content from MCP response format
            content = result.get("content", [])
            if content and len(content) > 0:
                # Return text content if available
                text_parts = [
                    c.get("text", "") for c in content if c.get("type") == "text"
                ]
                if text_parts:
                    return "\n".join(text_parts)

            # Return raw result if no text content
            return result

        except Exception as e:
            logger.error(
                "mcp_tool_call_error", name=self.name, tool=tool_name, error=str(e)
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
            except Exception as e:
                logger.error("mcp_disconnect_error", name=self.name, error=str(e))

        self.connected = False
        logger.info("mcp_server_disconnected", name=self.name)

    async def _send_request(
        self, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("Process not running")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        # Write request
        request_line = json.dumps(request) + "\n"
        self.process.stdin.write(request_line.encode())
        await self.process.stdin.drain()

        logger.debug(
            "mcp_request_sent",
            name=self.name,
            method=method,
            request_id=self._request_id,
        )

        # Read response (with timeout)
        try:
            response_line = await asyncio.wait_for(
                self.process.stdout.readline(),
                timeout=30.0,
            )

            if not response_line:
                raise RuntimeError("Process closed stdout")

            response = json.loads(response_line.decode())
            logger.debug(
                "mcp_response_received",
                name=self.name,
                request_id=self._request_id,
            )

            return response

        except TimeoutError:
            logger.error("mcp_request_timeout", name=self.name, method=method)
            return {"error": {"message": "Request timeout"}}
        except Exception as e:
            logger.error(
                "mcp_request_error", name=self.name, method=method, error=str(e)
            )
            return {"error": {"message": str(e)}}

    async def _send_notification(
        self, method: str, params: dict[str, Any] | None = None
    ):
        """Send a JSON-RPC notification (no response expected)."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not running")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }

        if params:
            notification["params"] = params

        notification_line = json.dumps(notification) + "\n"
        self.process.stdin.write(notification_line.encode())
        await self.process.stdin.drain()

        logger.debug("mcp_notification_sent", name=self.name, method=method)

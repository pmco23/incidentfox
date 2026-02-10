"""
Sandbox Server - FastAPI runtime running inside sandbox container on port 8888.

This server exposes endpoints for executing and interrupting investigations.
It maintains persistent agent sessions per thread_id to enable interrupts.

Streams structured events via SSE (Server-Sent Events) for client consumption.

Key features:
- **Config-driven**: Loads team config from Config Service via TEAM_TOKEN
- **Multi-LLM support**: Claude, Gemini, OpenAI via LiteLLM (OpenHandsProvider)
- **Conversation persistence**: Sessions maintain full conversation history across calls

Endpoints:
- GET /health - Health check
- GET /config - View loaded configuration (debug)
- POST /execute - Execute investigation (streaming SSE)
- POST /interrupt - Interrupt current execution
- POST /answer - Provide answer to AskUserQuestion
"""

import asyncio
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.config import Config, get_config, reload_config
from ..core.events import (
    error_event,
    result_event,
    thought_event,
)
from ..providers.base import LLMProvider, ProviderConfig, create_provider
from .manager import SandboxExecutionError, SandboxManager

logger = logging.getLogger(__name__)

app = FastAPI(
    title="IncidentFox Unified Agent Sandbox",
    description="Config-driven investigation agents with multi-LLM support",
    version="2.0.0",
)


# =============================================================================
# Session Management
# =============================================================================


@dataclass
class AgentSession:
    """
    Manages a persistent agent session for a thread.

    Sessions maintain:
    - OpenHandsProvider with conversation history
    - Interrupt flag for cancellation
    """

    thread_id: str
    provider: Optional[LLMProvider] = None
    is_running: bool = False
    _interrupt_flag: bool = False

    def interrupt(self):
        """Signal the session to stop."""
        self._interrupt_flag = True
        self.is_running = False

    def reset_interrupt(self):
        """Reset interrupt flag for new execution."""
        self._interrupt_flag = False

    @property
    def was_interrupted(self) -> bool:
        return self._interrupt_flag


# Global session manager: thread_id -> AgentSession
_sessions: Dict[str, AgentSession] = {}
_session_lock = asyncio.Lock()

# Sandbox manager (lazy initialized, used when USE_GVISOR=true)
_sandbox_manager: Optional[SandboxManager] = None

# File proxy: token -> download info mapping
_file_download_tokens: Dict[str, dict] = {}
_FILE_TOKEN_TTL_SECONDS = 3600  # 1 hour


def _is_sandbox_mode() -> bool:
    """Check if running in sandbox manager mode (creates gVisor pods)."""
    return os.getenv("USE_GVISOR", "false").lower() == "true"


def _get_sandbox_manager() -> SandboxManager:
    """Get or create the sandbox manager."""
    global _sandbox_manager
    if _sandbox_manager is None:
        namespace = os.getenv("SANDBOX_NAMESPACE") or os.getenv("NAMESPACE", "default")
        image = os.getenv("SANDBOX_IMAGE") or os.getenv("UNIFIED_AGENT_IMAGE")
        _sandbox_manager = SandboxManager(namespace=namespace, image=image)
    return _sandbox_manager


def _create_file_download_token(
    download_url: str, auth_header: str, filename: str, size: int
) -> str:
    """Create a secure download token for file proxy."""
    token = secrets.token_urlsafe(32)
    _file_download_tokens[token] = {
        "download_url": download_url,
        "auth_header": auth_header,
        "filename": filename,
        "size": size,
        "created_at": time.time(),
    }
    return token


def _cleanup_expired_tokens():
    """Remove expired download tokens."""
    current_time = time.time()
    expired = [
        token
        for token, info in _file_download_tokens.items()
        if current_time - info["created_at"] > _FILE_TOKEN_TTL_SECONDS
    ]
    for token in expired:
        del _file_download_tokens[token]


def _get_proxy_base_url() -> str:
    """
    Get the base URL for file proxy that sandbox can access.

    In K8s production: http://unified-agent-svc.<namespace>.svc.cluster.local:8888
    Local dev: http://host.docker.internal:8888
    """
    proxy_url = os.getenv("FILE_PROXY_URL")
    if proxy_url:
        return proxy_url

    if os.getenv("ROUTER_LOCAL_PORT"):
        return "http://host.docker.internal:8888"

    server_namespace = os.getenv("SERVER_NAMESPACE", os.getenv("NAMESPACE", "default"))
    return f"http://unified-agent-svc.{server_namespace}.svc.cluster.local:8888"


def _download_files_from_proxy(
    file_downloads: list[dict], thread_id: str
) -> list[str]:
    """
    Download file attachments from the proxy server into the sandbox filesystem.

    Files are saved to /workspace/attachments/{filename}
    """
    def format_size(bytes_val: int) -> str:
        if bytes_val >= 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f} MB"
        elif bytes_val >= 1024:
            return f"{bytes_val / 1024:.1f} KB"
        return f"{bytes_val} bytes"

    attachments_dir = Path("/workspace/attachments")
    attachments_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for download in file_downloads:
        safe_filename = Path(download["filename"]).name
        if not safe_filename:
            safe_filename = "unnamed_file"

        file_path = attachments_dir / safe_filename

        # Handle duplicate filenames
        counter = 1
        original_stem = file_path.stem
        original_suffix = file_path.suffix
        while file_path.exists():
            file_path = attachments_dir / f"{original_stem}_{counter}{original_suffix}"
            counter += 1

        error_path = attachments_dir / f"{file_path.name}.error"

        try:
            proxy_url = download["proxy_url"]
            logger.info(
                f"[SANDBOX] Downloading {download['filename']} "
                f"({format_size(download['size'])}) from proxy..."
            )

            with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
                with client.stream("GET", proxy_url) as response:
                    if response.status_code != 200:
                        error_msg = f"HTTP {response.status_code}"
                        logger.warning(
                            f"[SANDBOX] Failed to download {download['filename']}: {error_msg}"
                        )
                        error_path.write_text(
                            f"Download failed for: {download['filename']}\n"
                            f"Error: {error_msg}\n"
                        )
                        continue

                    bytes_written = 0
                    with open(file_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=65536):
                            f.write(chunk)
                            bytes_written += len(chunk)

            saved_paths.append(str(file_path))
            logger.info(
                f"[SANDBOX] Saved: {file_path} ({format_size(bytes_written)})"
            )

        except Exception as e:
            logger.warning(f"[SANDBOX] Failed to download {download['filename']}: {e}")
            try:
                error_path.write_text(
                    f"Download failed for: {download['filename']}\n"
                    f"Error: {str(e)}\n"
                    f"\nThe file could not be downloaded. "
                    f"Please ask the user to re-upload or share the content directly.\n"
                )
            except Exception:
                pass

    return saved_paths


async def _async_stream_response(response):
    """Convert sync streaming response to async generator.

    Reads chunks from a synchronous requests.Response in a thread pool
    to avoid blocking the async event loop.
    """

    def _get_next(it):
        try:
            return next(it)
        except StopIteration:
            return None

    it = response.iter_content(chunk_size=None)
    while True:
        chunk = await asyncio.to_thread(_get_next, it)
        if chunk is None:
            break
        yield chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk


def _get_root_agent_config(config: Config):
    """
    Get the root agent config from team config.

    Prefers 'investigator', then 'planner', then first available.
    Returns None if no team config or no agents configured.
    """
    if config.team_config is None:
        return None

    agents_config = config.team_config.agents_config
    return (
        agents_config.get("investigator")
        or agents_config.get("planner")
        or next(iter(agents_config.values()), None)
    )


def _get_allowed_tools(config: Config) -> list[str]:
    """
    Get allowed tools from team config or defaults.

    Maps team config tool settings to the tool names expected by OpenHandsProvider.
    """
    default_tools = [
        "Bash",
        "Read",
        "Write",
        "Edit",
        "Glob",
        "Grep",
        "WebSearch",
        "WebFetch",
        "Skill",
        "Task",
    ]

    root_config = _get_root_agent_config(config)
    if root_config is None:
        return default_tools

    enabled = root_config.tools.enabled
    if "*" in enabled:
        if root_config.tools.disabled:
            return [t for t in default_tools if t not in root_config.tools.disabled]
        return default_tools

    return enabled


def _get_system_prompt(config: Config) -> Optional[str]:
    """
    Get custom system prompt from team config, if any.

    Returns the root agent's system prompt, or None for default.
    """
    root_config = _get_root_agent_config(config)
    if root_config is None:
        return None

    return root_config.prompt.system or None


async def get_or_create_session(thread_id: str) -> AgentSession:
    """
    Get existing session or create new one for thread_id.

    Creates an OpenHandsProvider-based session that maintains conversation
    history across calls, enabling multi-turn investigations.
    """
    async with _session_lock:
        if thread_id not in _sessions:
            config = get_config()

            system_prompt = _get_system_prompt(config)
            provider_config = ProviderConfig(
                cwd=os.getenv("WORKSPACE_DIR", "/workspace"),
                thread_id=thread_id,
                model=config.llm_model,
                allowed_tools=_get_allowed_tools(config),
                system_prompt=system_prompt,
            )

            provider = create_provider(provider_config)
            await provider.start()

            session = AgentSession(thread_id=thread_id, provider=provider)
            _sessions[thread_id] = session
            logger.info(
                f"Created session {thread_id} with model: {config.llm_model}"
                f", custom_prompt: {bool(system_prompt)}"
            )

        return _sessions[thread_id]


# =============================================================================
# Request/Response Models
# =============================================================================


class ImageData(BaseModel):
    """Image data for multimodal input."""

    type: str = "base64"
    media_type: str
    data: str
    filename: Optional[str] = None


class FileDownloadData(BaseModel):
    """File download info for proxy-based download (sent to sandbox pod)."""

    token: str
    filename: str
    size: int
    media_type: str
    proxy_url: str


class ExecuteRequest(BaseModel):
    """Request to execute an investigation."""

    prompt: str
    thread_id: Optional[str] = None
    images: Optional[List[ImageData]] = None
    file_downloads: Optional[List[FileDownloadData]] = None
    agent: Optional[str] = None  # Specific agent to use (default: root)
    max_turns: Optional[int] = None


class FileAttachment(BaseModel):
    """File attachment metadata from slack-bot for proxy-based download."""

    filename: str
    size: int
    media_type: str
    download_url: str
    auth_header: str


class InvestigateRequest(BaseModel):
    """
    Request to investigate - compatibility endpoint for slack-bot.

    This model accepts the legacy /investigate request format used by slack-bot,
    which includes team_token in the request body instead of environment.
    """

    prompt: str
    thread_id: Optional[str] = None
    tenant_id: Optional[str] = None  # Slack team_id for credential lookup
    team_id: Optional[str] = None  # Slack team_id
    team_token: Optional[str] = None  # Team token for config loading
    images: Optional[List[ImageData]] = None
    file_attachments: Optional[List[FileAttachment]] = None


class InterruptRequest(BaseModel):
    """Request to interrupt the investigation."""

    thread_id: str


class AnswerRequest(BaseModel):
    """Request to provide answer to AskUserQuestion."""

    thread_id: str
    answers: dict


# =============================================================================
# Endpoints
# =============================================================================


@app.get("/health")
async def health():
    """Health check endpoint."""
    config = get_config()
    return {
        "status": "healthy",
        "service": "unified-agent-sandbox",
        "version": "2.0.0",
        "mode": "sandbox-manager" if _is_sandbox_mode() else "direct",
        "active_sessions": len(_sessions),
        "model": config.llm_model,
        "tenant_id": config.tenant_id,
        "team_id": config.team_id,
        "config_loaded": config.team_config is not None,
    }


@app.get("/proxy/files/{token}")
async def proxy_file_download(token: str):
    """
    File proxy endpoint - streams files from external sources (e.g., Slack).

    Allows sandboxes to download files without having access to actual credentials.
    Tokens are single-use and expire after 1 hour.
    """
    _cleanup_expired_tokens()

    if token not in _file_download_tokens:
        raise HTTPException(
            status_code=404, detail="Download token not found or expired"
        )

    token_info = _file_download_tokens[token]
    download_url = token_info["download_url"]
    auth_header = token_info["auth_header"]
    filename = token_info["filename"]

    logger.info(f"[PROXY] Downloading file: {filename}")

    async def stream_file():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                async with client.stream(
                    "GET", download_url, headers={"Authorization": auth_header}
                ) as response:
                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Failed to download from source: {response.status_code}",
                        )

                    bytes_streamed = 0
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        bytes_streamed += len(chunk)
                        yield chunk

                    logger.info(
                        f"[PROXY] Completed streaming {filename}: {bytes_streamed} bytes"
                    )

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504, detail="Timeout downloading file from source"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[PROXY] Error streaming {filename}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error downloading file: {str(e)}"
            )

    # Delete token after starting download (single-use)
    del _file_download_tokens[token]

    # Sanitize filename for Content-Disposition header (prevent header injection)
    safe_filename = filename.replace('"', '\\"').replace("\r", "").replace("\n", "")

    return StreamingResponse(
        stream_file(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
        },
    )


@app.get("/config")
async def get_loaded_config():
    """
    View the loaded configuration (for debugging).

    Shows provider settings and active sessions.
    """
    config = get_config()

    return {
        "tenant_id": config.tenant_id,
        "team_id": config.team_id,
        "llm_model": config.llm_model,
        "config_source": "config_service" if os.getenv("TEAM_TOKEN") else "local",
        "allowed_tools": _get_allowed_tools(config),
        "active_sessions": len(_sessions),
    }


@app.post("/config/reload")
async def reload_configuration():
    """
    Force reload of configuration from Config Service.

    Useful after config changes to pick up new agent settings.
    Clears all sessions so new ones are created with updated config.
    """
    # Close existing sessions
    async with _session_lock:
        for session in _sessions.values():
            if session.provider:
                await session.provider.close()
        _sessions.clear()

    # Reload config
    reload_config()
    config = get_config()

    return {
        "status": "reloaded",
        "model": config.llm_model,
        "tools": _get_allowed_tools(config),
    }


@app.get("/sessions")
async def list_sessions():
    """List active sessions (for debugging)."""
    return {
        "sessions": [
            {
                "thread_id": thread_id,
                "is_running": session.is_running,
                "has_provider": session.provider is not None,
                "history_length": (
                    len(session.provider._conversation_history)
                    if session.provider
                    and hasattr(session.provider, "_conversation_history")
                    else 0
                ),
            }
            for thread_id, session in _sessions.items()
        ]
    }


@app.post("/execute")
async def execute(request: ExecuteRequest):
    """
    Execute an investigation agent with the given prompt (streaming SSE).

    The agent is built from team configuration loaded via TEAM_TOKEN.
    Supports multi-LLM (Claude, Gemini, OpenAI) based on config.
    """
    thread_id = request.thread_id or os.getenv("THREAD_ID", "default")

    # Get or create session
    try:
        session = await get_or_create_session(thread_id)
    except Exception as e:
        logger.error(f"Failed to create session: {e}")

        async def error_stream():
            yield error_event(
                thread_id, f"Failed to initialize: {e}", recoverable=False
            ).to_sse()

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Reset interrupt flag
    session.reset_interrupt()
    session.is_running = True

    # Download file attachments from proxy BEFORE starting agent
    if request.file_downloads:
        logger.info(
            f"Downloading {len(request.file_downloads)} file(s) for thread {thread_id}"
        )
        file_download_dicts = [fd.model_dump() for fd in request.file_downloads]
        saved_paths = _download_files_from_proxy(file_download_dicts, thread_id)
        logger.info(f"Downloaded {len(saved_paths)} file(s): {saved_paths}")

    # Build images list for multimodal input
    images_list = None
    if request.images:
        images_list = [
            {
                "type": img.type,
                "media_type": img.media_type,
                "data": img.data,
            }
            for img in request.images
        ]

    async def stream():
        try:
            logger.info(f"Starting execution for thread {thread_id}")
            event_count = 0

            # Stream events from provider (maintains conversation history)
            async for event in session.provider.execute(
                request.prompt,
                images=images_list,
            ):
                if session.was_interrupted:
                    yield thought_event(thread_id, "Execution interrupted.").to_sse()
                    yield result_event(
                        thread_id,
                        "Task interrupted. Send a new message to continue.",
                        success=True,
                        subtype="interrupted",
                    ).to_sse()
                    break

                event_count += 1

                if hasattr(event, "to_sse"):
                    yield event.to_sse()
                else:
                    yield f"data: {json.dumps({'type': 'unknown', 'data': str(event)})}\n\n"

            logger.info(
                f"Execution completed: {event_count} events for thread {thread_id}"
            )

        except Exception as e:
            logger.error(f"Execution error for {thread_id}: {e}", exc_info=True)
            yield error_event(
                thread_id, f"Execution failed: {e}", recoverable=False
            ).to_sse()

        finally:
            session.is_running = False

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/investigate")
async def investigate(request: InvestigateRequest):
    """
    Investigation endpoint - routes to sandbox or direct execution.

    In sandbox mode (USE_GVISOR=true):
      - Creates/reuses gVisor sandbox pod via SandboxManager
      - Routes request through sandbox-router
      - Credentials injected via Envoy sidecar + credential-resolver

    In direct mode:
      - Executes agent locally (no isolation)
    """
    if _is_sandbox_mode():
        return await _investigate_via_sandbox(request)
    return await _investigate_direct(request)


async def _investigate_direct(request: InvestigateRequest):
    """Execute investigation directly in this process (no sandbox)."""
    # Set team_token as env var if provided (for config service auth)
    if request.team_token:
        os.environ["TEAM_TOKEN"] = request.team_token
        logger.info(f"Set TEAM_TOKEN from request for thread {request.thread_id}")

        # Reload config to pick up new team token
        reload_config()

    # In direct mode, process file_attachments locally (create download tokens
    # so the download logic in /execute can handle them)
    file_downloads = None
    if request.file_attachments:
        proxy_base_url = _get_proxy_base_url()
        file_downloads = []
        for att in request.file_attachments:
            token = _create_file_download_token(
                download_url=att.download_url,
                auth_header=att.auth_header,
                filename=att.filename,
                size=att.size,
            )
            file_downloads.append(
                FileDownloadData(
                    token=token,
                    filename=att.filename,
                    size=att.size,
                    media_type=att.media_type,
                    proxy_url=f"{proxy_base_url}/proxy/files/{token}",
                )
            )
            logger.info(f"Created download token for {att.filename} ({att.size} bytes)")

    # Forward to execute with compatible fields
    execute_request = ExecuteRequest(
        prompt=request.prompt,
        thread_id=request.thread_id,
        images=request.images,
        file_downloads=file_downloads,
    )
    return await execute(execute_request)


async def _investigate_via_sandbox(request: InvestigateRequest):
    """Execute investigation in an isolated gVisor sandbox pod."""
    thread_id = request.thread_id or f"inv-{int(time.time())}"
    tenant_id = request.tenant_id or os.getenv("INCIDENTFOX_TENANT_ID", "default")
    team_id = request.team_id or os.getenv("INCIDENTFOX_TEAM_ID", "default")

    manager = _get_sandbox_manager()

    # Process file attachments: create download tokens for sandbox to fetch via proxy
    file_downloads = None
    if request.file_attachments:
        proxy_base_url = _get_proxy_base_url()
        file_downloads = []
        for att in request.file_attachments:
            token = _create_file_download_token(
                download_url=att.download_url,
                auth_header=att.auth_header,
                filename=att.filename,
                size=att.size,
            )
            file_downloads.append(
                {
                    "token": token,
                    "filename": att.filename,
                    "size": att.size,
                    "media_type": att.media_type,
                    "proxy_url": f"{proxy_base_url}/proxy/files/{token}",
                }
            )
            logger.info(f"Created download token for {att.filename} ({att.size} bytes)")
        logger.info(f"Total {len(file_downloads)} file download(s) prepared")

    async def stream():
        try:
            # Check for existing sandbox for this thread
            sandbox_info = await asyncio.to_thread(manager.get_sandbox, thread_id)

            if sandbox_info is None:
                yield thought_event(thread_id, "Creating isolated sandbox...").to_sse()

                sandbox_info = await asyncio.to_thread(
                    manager.create_sandbox,
                    thread_id=thread_id,
                    tenant_id=tenant_id,
                    team_id=team_id,
                    team_token=request.team_token,
                )

                yield thought_event(
                    thread_id, "Waiting for sandbox to be ready..."
                ).to_sse()

                ready = await asyncio.to_thread(manager.wait_for_ready, thread_id, 120)
                if not ready:
                    yield error_event(
                        thread_id,
                        "Sandbox failed to start within timeout",
                        recoverable=False,
                    ).to_sse()
                    return

                yield thought_event(
                    thread_id, "Sandbox ready. Starting investigation..."
                ).to_sse()

            # Execute in sandbox via router (streaming SSE)
            images = (
                [img.model_dump() for img in request.images] if request.images else None
            )
            response = await asyncio.to_thread(
                manager.execute_in_sandbox,
                sandbox_info,
                request.prompt,
                images,
                file_downloads,
            )

            # Forward SSE stream from sandbox pod
            async for chunk in _async_stream_response(response):
                yield chunk

        except SandboxExecutionError as e:
            logger.error(f"Sandbox execution failed: {e}", exc_info=True)
            yield error_event(thread_id, str(e), recoverable=False).to_sse()
        except Exception as e:
            logger.error(f"Sandbox error: {e}", exc_info=True)
            yield error_event(
                thread_id, f"Sandbox error: {e}", recoverable=False
            ).to_sse()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/interrupt")
async def interrupt(request: InterruptRequest):
    """
    Interrupt the current execution and stop.

    After interrupt, new messages can be sent via execute endpoint.
    """
    if _is_sandbox_mode():
        return await _interrupt_via_sandbox(request)
    return await _interrupt_direct(request)


async def _interrupt_direct(request: InterruptRequest):
    """Interrupt a local execution."""
    thread_id = request.thread_id

    async def stream():
        try:
            async with _session_lock:
                if thread_id not in _sessions:
                    yield error_event(
                        thread_id, "No active session found", recoverable=False
                    ).to_sse()
                    return
                session = _sessions[thread_id]

            # Signal interrupt
            session.interrupt()

            yield thought_event(thread_id, "Interrupting current task...").to_sse()
            yield result_event(
                thread_id,
                "Task interrupted. Send a new message to continue.",
                success=True,
                subtype="interrupted",
            ).to_sse()

        except Exception as e:
            yield error_event(
                thread_id, f"Interrupt failed: {e}", recoverable=False
            ).to_sse()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _interrupt_via_sandbox(request: InterruptRequest):
    """Interrupt an execution running in a sandbox pod."""
    thread_id = request.thread_id
    manager = _get_sandbox_manager()

    async def stream():
        try:
            sandbox_info = await asyncio.to_thread(manager.get_sandbox, thread_id)
            if sandbox_info is None:
                yield error_event(
                    thread_id, "No active sandbox found", recoverable=False
                ).to_sse()
                return

            response = await asyncio.to_thread(manager.interrupt_sandbox, sandbox_info)

            # Forward SSE stream from sandbox
            async for chunk in _async_stream_response(response):
                yield chunk

        except Exception as e:
            logger.error(f"Sandbox interrupt failed: {e}", exc_info=True)
            yield error_event(
                thread_id, f"Interrupt failed: {e}", recoverable=False
            ).to_sse()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/answer")
async def answer_question(request: AnswerRequest):
    """Receive answer to AskUserQuestion from main server."""
    thread_id = request.thread_id

    async with _session_lock:
        if thread_id not in _sessions:
            raise HTTPException(404, f"No active session for {thread_id}")
        # Note: Answer handling requires additional state management
        # This is a placeholder for future implementation

    return {"status": "ok", "thread_id": thread_id, "note": "Answer queued"}


@app.post("/cleanup")
async def cleanup_session(thread_id: str):
    """Manually cleanup a session."""
    async with _session_lock:
        if thread_id in _sessions:
            session = _sessions.pop(thread_id)
            session.interrupt()
            if session.provider:
                await session.provider.close()
            return {"status": "cleaned", "thread_id": thread_id}
        return {"status": "not_found", "thread_id": thread_id}


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    config = get_config()
    sandbox_mode = _is_sandbox_mode()
    logger.info("Sandbox server starting...")
    logger.info(f"  Mode: {'sandbox-manager' if sandbox_mode else 'direct'}")
    logger.info(f"  Tenant: {config.tenant_id}")
    logger.info(f"  Team: {config.team_id}")
    logger.info(f"  Model: {config.llm_model}")
    logger.info(f"  Config loaded: {config.team_config is not None}")

    if sandbox_mode:
        logger.info(f"  Sandbox image: {os.getenv('SANDBOX_IMAGE', 'not set')}")
        logger.info(f"  Sandbox namespace: {os.getenv('SANDBOX_NAMESPACE', 'not set')}")
        logger.info(f"  gVisor: {os.getenv('USE_GVISOR', 'false')}")
    else:
        logger.info("  Provider: OpenHands (LiteLLM)")
        logger.info(f"  Allowed tools: {_get_allowed_tools(config)}")
        logger.info(f"  Workspace: {os.getenv('WORKSPACE_DIR', '/workspace')}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up all sessions on shutdown."""
    async with _session_lock:
        for session in _sessions.values():
            session.interrupt()
            if session.provider:
                await session.provider.close()
        _sessions.clear()


def run_server():
    """Run the sandbox server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8888, log_level="info")


if __name__ == "__main__":
    run_server()

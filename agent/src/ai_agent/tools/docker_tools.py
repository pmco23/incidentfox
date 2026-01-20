"""
Docker tools for container operations.

Ported from cto-ai-agent, adapted for OpenAI Agents SDK.
Provides Docker CLI access for container debugging and management.
"""

from __future__ import annotations

import json
import subprocess

from agents import function_tool

from ..core.logging import get_logger

logger = get_logger(__name__)


def _run_docker(
    args: list[str],
    cwd: str | None = None,
    timeout_s: float = 300.0,
) -> dict:
    """Run a docker command and return structured output."""
    cmd = ["docker"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout[-20000:] if result.stdout else "",
            "stderr": result.stderr[-5000:] if result.stderr else "",
            "cmd": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "cmd": " ".join(cmd)}
    except FileNotFoundError:
        return {"ok": False, "error": "docker_not_found", "cmd": " ".join(cmd)}
    except Exception as e:
        return {"ok": False, "error": str(e), "cmd": " ".join(cmd)}


@function_tool
def docker_ps(all_containers: bool = False) -> str:
    """
    List Docker containers.

    Use cases:
    - Check running containers
    - Find container IDs
    - Debug container status

    Args:
        all_containers: Include stopped containers (default False)

    Returns:
        JSON with containers list
    """
    logger.info("docker_ps", all_containers=all_containers)

    args = ["ps", "--format", "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}"]
    if all_containers:
        args.append("-a")

    result = _run_docker(args)

    if result.get("ok"):
        containers = []
        for line in result.get("stdout", "").strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 4:
                    containers.append(
                        {
                            "id": parts[0],
                            "name": parts[1],
                            "image": parts[2],
                            "status": parts[3],
                            "ports": parts[4] if len(parts) > 4 else "",
                        }
                    )
        result["containers"] = containers

    return json.dumps(result)


@function_tool
def docker_logs(container: str, tail: int = 100) -> str:
    """
    Get container logs.

    Use cases:
    - Debug container issues
    - Check application output
    - Find error messages

    Args:
        container: Container name or ID
        tail: Number of lines from the end (default 100)

    Returns:
        JSON with logs content
    """
    if not container:
        return json.dumps({"ok": False, "error": "container is required"})

    logger.info("docker_logs", container=container, tail=tail)

    result = _run_docker(["logs", "--tail", str(tail), container])
    if result.get("ok"):
        result["logs"] = result.get("stdout", "") + result.get("stderr", "")
    return json.dumps(result)


@function_tool
def docker_inspect(container: str) -> str:
    """
    Get detailed container information.

    Use cases:
    - Check container configuration
    - Debug networking issues
    - Verify environment variables

    Args:
        container: Container name or ID

    Returns:
        JSON with container details
    """
    if not container:
        return json.dumps({"ok": False, "error": "container is required"})

    logger.info("docker_inspect", container=container)
    result = _run_docker(["inspect", container])

    if result.get("ok"):
        try:
            result["inspection"] = json.loads(result.get("stdout", "[]"))
        except json.JSONDecodeError:
            result["inspection"] = []

    return json.dumps(result)


@function_tool
def docker_exec(container: str, command: str, workdir: str = "") -> str:
    """
    Execute a command in a running container.

    Use cases:
    - Debug running containers
    - Check files inside container
    - Run diagnostic commands

    Args:
        container: Container name or ID
        command: Command to run (e.g., "ls -la /app")
        workdir: Working directory inside container

    Returns:
        JSON with command output
    """
    if not container or not command:
        return json.dumps({"ok": False, "error": "container and command are required"})

    logger.info("docker_exec", container=container, command=command[:50])

    args = ["exec"]
    if workdir:
        args.extend(["-w", workdir])
    args.append(container)
    args.extend(["sh", "-c", command])

    result = _run_docker(args)
    return json.dumps(result)


@function_tool
def docker_images(filter_str: str = "") -> str:
    """
    List Docker images.

    Use cases:
    - Check available images
    - Find image IDs
    - Verify image versions

    Args:
        filter_str: Filter pattern (e.g., "reference=myapp*")

    Returns:
        JSON with images list
    """
    logger.info("docker_images", filter_str=filter_str)

    args = [
        "images",
        "--format",
        "{{.Repository}}|{{.Tag}}|{{.ID}}|{{.Size}}|{{.CreatedAt}}",
    ]
    if filter_str:
        args.extend(["--filter", filter_str])

    result = _run_docker(args)

    if result.get("ok"):
        images = []
        for line in result.get("stdout", "").strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 4:
                    images.append(
                        {
                            "repository": parts[0],
                            "tag": parts[1],
                            "id": parts[2],
                            "size": parts[3],
                            "created": parts[4] if len(parts) > 4 else "",
                        }
                    )
        result["images"] = images

    return json.dumps(result)


@function_tool
def docker_stats(container: str = "") -> str:
    """
    Get container resource usage statistics.

    Use cases:
    - Check CPU/memory usage
    - Debug performance issues
    - Monitor resource consumption

    Args:
        container: Specific container (optional, shows all if empty)

    Returns:
        JSON with resource stats
    """
    logger.info("docker_stats", container=container)

    args = [
        "stats",
        "--no-stream",
        "--format",
        "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}|{{.BlockIO}}",
    ]
    if container:
        args.append(container)

    result = _run_docker(args, timeout_s=30.0)

    if result.get("ok"):
        stats = []
        for line in result.get("stdout", "").strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 4:
                    stats.append(
                        {
                            "name": parts[0],
                            "cpu": parts[1],
                            "memory": parts[2],
                            "net_io": parts[3],
                            "block_io": parts[4] if len(parts) > 4 else "",
                        }
                    )
        result["stats"] = stats

    return json.dumps(result)


@function_tool
def docker_compose_ps(file: str = "docker-compose.yml", cwd: str = ".") -> str:
    """
    List Docker Compose services.

    Args:
        file: Compose file path
        cwd: Working directory

    Returns:
        JSON with services list
    """
    logger.info("docker_compose_ps", file=file)

    args = ["compose", "-f", file, "ps", "--format", "json"]
    result = _run_docker(args, cwd=cwd or None)

    if result.get("ok"):
        try:
            result["services"] = json.loads(result.get("stdout", "[]"))
        except json.JSONDecodeError:
            result["services"] = []

    return json.dumps(result)


@function_tool
def docker_compose_logs(
    file: str = "docker-compose.yml",
    services: str = "",
    tail: int = 100,
    cwd: str = ".",
) -> str:
    """
    Get logs from Docker Compose services.

    Args:
        file: Compose file path
        services: Comma-separated service names (optional)
        tail: Number of lines
        cwd: Working directory

    Returns:
        JSON with logs content
    """
    logger.info("docker_compose_logs", file=file, services=services)

    args = ["compose", "-f", file, "logs", "--tail", str(tail)]
    if services:
        args.extend(services.split(","))

    result = _run_docker(args, cwd=cwd or None)
    if result.get("ok"):
        result["logs"] = result.get("stdout", "")
    return json.dumps(result)

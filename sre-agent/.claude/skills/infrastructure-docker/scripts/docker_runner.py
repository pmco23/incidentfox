#!/usr/bin/env python3
"""Shared Docker command runner.

Provides subprocess-based Docker CLI execution with structured output.
"""

import json
import subprocess
from typing import Any


_ALLOWED_SUBCOMMANDS = frozenset({
    "ps", "logs", "inspect", "stats", "top", "events", "diff",
    "images", "info", "version", "network", "volume", "compose",
    "container", "image", "system",
})


def run_docker(
    args: list[str],
    cwd: str | None = None,
    timeout_s: float = 300.0,
) -> dict[str, Any]:
    """Run a docker command and return structured output."""
    subcmd = args[0] if args else ""
    if subcmd not in _ALLOWED_SUBCOMMANDS:
        allowed = ", ".join(sorted(_ALLOWED_SUBCOMMANDS))
        return {
            "ok": False,
            "error": f"Subcommand '{subcmd}' not allowed. Allowed: {allowed}",
            "cmd": f"docker {' '.join(args)}",
        }
    cmd = ["docker"] + args
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s
        )
        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout[-20000:] if result.stdout else "",
            "stderr": result.stderr[-5000:] if result.stderr else "",
            "cmd": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Command timed out", "cmd": " ".join(cmd)}
    except FileNotFoundError:
        return {"ok": False, "error": "docker not found in PATH", "cmd": " ".join(cmd)}
    except Exception as e:
        return {"ok": False, "error": str(e), "cmd": " ".join(cmd)}


def parse_pipe_delimited(output: str, field_names: list[str]) -> list[dict[str, str]]:
    """Parse pipe-delimited docker format output into list of dicts."""
    items = []
    for line in output.strip().split("\n"):
        if line:
            parts = line.split("|")
            if len(parts) >= len(field_names):
                items.append({name: parts[i] for i, name in enumerate(field_names)})
    return items

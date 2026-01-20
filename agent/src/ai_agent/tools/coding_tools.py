"""
Coding tools for code search, testing, and analysis.

Ported from cto-ai-agent, adapted for OpenAI Agents SDK.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from agents import function_tool

from ..core.logging import get_logger

logger = get_logger(__name__)


@function_tool
def repo_search_text(
    pattern: str, glob_pattern: str = "**/*", cwd: str = ".", max_matches: int = 50
) -> str:
    """
    Search for a regex pattern in workspace files.

    Use cases:
    - Find where a function/class is defined
    - Search for error messages
    - Find all usages of a variable/pattern

    Args:
        pattern: Regex pattern to search for
        glob_pattern: File pattern (e.g., "**/*.py", "*.js")
        cwd: Directory to search in
        max_matches: Maximum number of matches to return

    Returns:
        JSON with matches list containing path, line number, and text
    """
    if not pattern:
        return json.dumps({"ok": False, "error": "pattern is required"})

    logger.info("repo_search_text", pattern=pattern[:50], glob=glob_pattern)

    root = Path(cwd) if cwd else Path(".")
    if not root.exists():
        return json.dumps({"ok": False, "error": f"Directory not found: {root}"})

    try:
        rx = re.compile(pattern)
    except re.error as e:
        return json.dumps({"ok": False, "error": f"Invalid regex: {e}"})

    max_file_bytes = 512_000  # 512KB
    matches: list[dict] = []

    for fp in root.glob(glob_pattern):
        if not fp.is_file():
            continue
        # Skip common non-code directories
        if any(
            part.startswith(".")
            or part in ("node_modules", "venv", "__pycache__", "dist", "build")
            for part in fp.parts
        ):
            continue
        try:
            if fp.stat().st_size > max_file_bytes:
                continue
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                matches.append(
                    {
                        "path": str(fp.relative_to(root) if cwd else fp),
                        "line": i,
                        "text": line[:400],
                    }
                )
                if len(matches) >= max_matches:
                    return json.dumps(
                        {"ok": True, "matches": matches, "truncated": True}
                    )

    return json.dumps({"ok": True, "matches": matches, "truncated": False})


@function_tool
def python_run_tests(
    test_dir: str = "tests",
    pattern: str = "test_*.py",
    timeout_s: int = 180,
    cwd: str = ".",
) -> str:
    """
    Run Python unit tests using unittest discovery.

    Use cases:
    - Verify code changes don't break tests
    - Run specific test files
    - Debug test failures

    Args:
        test_dir: Directory containing tests (default "tests")
        pattern: Test file pattern (default "test_*.py")
        timeout_s: Timeout in seconds
        cwd: Working directory

    Returns:
        JSON with ok, returncode, and test output
    """
    logger.info("python_run_tests", test_dir=test_dir, pattern=pattern)

    cmd = ["python3", "-m", "unittest", "discover", "-s", test_dir, "-p", pattern, "-v"]
    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd or None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s,
        )
        return json.dumps(
            {
                "ok": cp.returncode == 0,
                "returncode": cp.returncode,
                "output": (cp.stdout or "")[-8000:],
                "cmd": " ".join(cmd),
            }
        )
    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "ok": False,
                "error": f"Timed out after {timeout_s}s",
                "cmd": " ".join(cmd),
            }
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e), "cmd": " ".join(cmd)})


@function_tool
def pytest_run(args: str = "", timeout_s: int = 300, cwd: str = ".") -> str:
    """
    Run tests using pytest.

    Use cases:
    - Run pytest test suites
    - Run specific tests with markers
    - Generate test reports

    Args:
        args: Additional pytest arguments (e.g., "-x -v tests/test_api.py")
        timeout_s: Timeout in seconds
        cwd: Working directory

    Returns:
        JSON with ok, returncode, and test output
    """
    logger.info("pytest_run", args=args[:50] if args else "")

    cmd = ["python3", "-m", "pytest"]
    if args:
        cmd.extend(args.split())

    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd or None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s,
        )
        return json.dumps(
            {
                "ok": cp.returncode == 0,
                "returncode": cp.returncode,
                "output": (cp.stdout or "")[-10000:],
                "cmd": " ".join(cmd),
            }
        )
    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "ok": False,
                "error": f"Timed out after {timeout_s}s",
                "cmd": " ".join(cmd),
            }
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e), "cmd": " ".join(cmd)})


@function_tool
def read_file(path: str, start_line: int = 0, end_line: int = 0) -> str:
    """
    Read a file's contents.

    Use cases:
    - Examine source code
    - Read configuration files
    - Check file contents

    Args:
        path: File path to read
        start_line: Start line (1-indexed, 0 = start of file)
        end_line: End line (0 = end of file)

    Returns:
        JSON with ok and file content
    """
    if not path:
        return json.dumps({"ok": False, "error": "path is required"})

    logger.info("read_file", path=path)

    try:
        fp = Path(path)
        if not fp.exists():
            return json.dumps({"ok": False, "error": f"File not found: {path}"})

        if fp.stat().st_size > 1_000_000:  # 1MB limit
            return json.dumps({"ok": False, "error": "File too large (>1MB)"})

        content = fp.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        if start_line > 0 or end_line > 0:
            start = max(0, start_line - 1)
            end = end_line if end_line > 0 else len(lines)
            lines = lines[start:end]
            content = "\n".join(lines)

        return json.dumps(
            {
                "ok": True,
                "path": path,
                "content": content[:50000],  # Limit output
                "total_lines": len(content.splitlines()),
            }
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@function_tool
def write_file(path: str, content: str, create_dirs: bool = True) -> str:
    """
    Write content to a file.

    Use cases:
    - Create new files
    - Update existing files
    - Save configuration

    Args:
        path: File path to write
        content: Content to write
        create_dirs: Create parent directories if needed

    Returns:
        JSON with ok and path
    """
    if not path:
        return json.dumps({"ok": False, "error": "path is required"})

    logger.info("write_file", path=path, content_len=len(content))

    try:
        fp = Path(path)
        if create_dirs:
            fp.parent.mkdir(parents=True, exist_ok=True)

        fp.write_text(content, encoding="utf-8")
        return json.dumps(
            {
                "ok": True,
                "path": path,
                "bytes_written": len(content.encode("utf-8")),
            }
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@function_tool
def list_directory(path: str = ".", pattern: str = "*", recursive: bool = False) -> str:
    """
    List files in a directory.

    Use cases:
    - Explore project structure
    - Find files by pattern
    - Check directory contents

    Args:
        path: Directory path
        pattern: Glob pattern (e.g., "*.py")
        recursive: Search recursively

    Returns:
        JSON with files list
    """
    logger.info("list_directory", path=path, pattern=pattern)

    try:
        root = Path(path)
        if not root.exists():
            return json.dumps({"ok": False, "error": f"Directory not found: {path}"})

        if recursive:
            glob_pattern = f"**/{pattern}"
        else:
            glob_pattern = pattern

        files = []
        for fp in root.glob(glob_pattern):
            # Skip hidden and common non-code directories
            if any(
                part.startswith(".") or part in ("node_modules", "venv", "__pycache__")
                for part in fp.parts
            ):
                continue

            files.append(
                {
                    "path": str(fp.relative_to(root)),
                    "type": "dir" if fp.is_dir() else "file",
                    "size": fp.stat().st_size if fp.is_file() else None,
                }
            )

            if len(files) >= 500:  # Limit
                break

        return json.dumps(
            {
                "ok": True,
                "path": path,
                "files": files,
                "count": len(files),
            }
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@function_tool
def run_linter(path: str = ".", tool: str = "ruff", fix: bool = False) -> str:
    """
    Run a linter on code.

    Use cases:
    - Check code quality
    - Find style issues
    - Auto-fix simple problems

    Args:
        path: File or directory to lint
        tool: Linter to use (ruff, flake8, eslint)
        fix: Apply auto-fixes

    Returns:
        JSON with linting results
    """
    logger.info("run_linter", path=path, tool=tool, fix=fix)

    if tool == "ruff":
        cmd = ["ruff", "check", path]
        if fix:
            cmd.append("--fix")
    elif tool == "flake8":
        cmd = ["flake8", path]
    elif tool == "eslint":
        cmd = ["npx", "eslint", path]
        if fix:
            cmd.append("--fix")
    else:
        return json.dumps({"ok": False, "error": f"Unknown linter: {tool}"})

    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return json.dumps(
            {
                "ok": cp.returncode == 0,
                "returncode": cp.returncode,
                "output": (cp.stdout or "")[-10000:],
                "errors": (cp.stderr or "")[-5000:],
                "cmd": " ".join(cmd),
            }
        )
    except FileNotFoundError:
        return json.dumps({"ok": False, "error": f"{tool} not found"})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@function_tool
def run_jest(args: str = "", timeout_s: int = 300, cwd: str = ".") -> str:
    """
    Run Jest tests.

    Use cases:
    - Run JavaScript/TypeScript unit tests
    - Verify test fixes
    - Run specific test files or suites

    Args:
        args: Additional Jest arguments (e.g., "--testPathPattern=auth", "--coverage")
        timeout_s: Timeout in seconds
        cwd: Working directory

    Returns:
        JSON with test results
    """
    logger.info("run_jest", args=args, cwd=cwd)

    import shlex

    cmd = ["npx", "jest"]
    if args:
        cmd.extend(shlex.split(args))

    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )

        stdout = cp.stdout or ""
        stderr = cp.stderr or ""
        combined = stdout + "\n" + stderr

        # Parse Jest output for pass/fail counts
        passed = failed = total = 0
        for line in combined.split("\n"):
            if "Tests:" in line:
                # Example: "Tests:       2 failed, 5 passed, 7 total"
                import re

                match = re.search(r"(\d+)\s+failed", line)
                if match:
                    failed = int(match.group(1))
                match = re.search(r"(\d+)\s+passed", line)
                if match:
                    passed = int(match.group(1))
                match = re.search(r"(\d+)\s+total", line)
                if match:
                    total = int(match.group(1))

        return json.dumps(
            {
                "ok": cp.returncode == 0,
                "returncode": cp.returncode,
                "output": combined[-15000:],
                "passed": passed,
                "failed": failed,
                "total": total,
                "cmd": " ".join(cmd),
            }
        )
    except FileNotFoundError:
        return json.dumps(
            {"ok": False, "error": "jest not found (try: npm install --save-dev jest)"}
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"ok": False, "error": f"timeout after {timeout_s}s"})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@function_tool
def run_eslint(path: str = ".", fix: bool = False, cwd: str = ".") -> str:
    """
    Run ESLint on JavaScript/TypeScript code.

    Use cases:
    - Check code style and quality
    - Find common errors
    - Auto-fix formatting issues

    Args:
        path: File or directory to lint
        fix: Apply auto-fixes
        cwd: Working directory

    Returns:
        JSON with linting results
    """
    logger.info("run_eslint", path=path, fix=fix, cwd=cwd)

    cmd = ["npx", "eslint", path]
    if fix:
        cmd.append("--fix")

    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return json.dumps(
            {
                "ok": cp.returncode == 0,
                "returncode": cp.returncode,
                "output": (cp.stdout or "")[-10000:],
                "errors": (cp.stderr or "")[-5000:],
                "cmd": " ".join(cmd),
            }
        )
    except FileNotFoundError:
        return json.dumps(
            {
                "ok": False,
                "error": "eslint not found (try: npm install --save-dev eslint)",
            }
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@function_tool
def run_prettier(
    path: str = ".", write: bool = False, check: bool = True, cwd: str = "."
) -> str:
    """
    Run Prettier code formatter on files.

    Use cases:
    - Check code formatting
    - Auto-format code
    - Fix formatting issues in CI

    Args:
        path: File or glob pattern (e.g., "src/**/*.ts")
        write: Write formatted output (default: False - check only)
        check: Check if files are formatted (default: True)
        cwd: Working directory

    Returns:
        JSON with formatting results
    """
    logger.info("run_prettier", path=path, write=write, check=check, cwd=cwd)

    cmd = ["npx", "prettier"]
    if write:
        cmd.append("--write")
    elif check:
        cmd.append("--check")
    cmd.append(path)

    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return json.dumps(
            {
                "ok": cp.returncode == 0,
                "returncode": cp.returncode,
                "output": (cp.stdout or "")[-10000:],
                "errors": (cp.stderr or "")[-5000:],
                "cmd": " ".join(cmd),
                "formatted": write,
            }
        )
    except FileNotFoundError:
        return json.dumps(
            {
                "ok": False,
                "error": "prettier not found (try: npm install --save-dev prettier)",
            }
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})

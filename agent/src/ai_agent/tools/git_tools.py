"""
Git tools for repository operations.

Ported from cto-ai-agent, adapted for OpenAI Agents SDK.
"""

from __future__ import annotations

import json
import subprocess

from agents import function_tool

from ..core.logging import get_logger

logger = get_logger(__name__)


def _run_git(
    args: list[str],
    cwd: str | None = None,
    timeout_s: float = 60.0,
) -> dict:
    """Run a git command and return structured output."""
    cmd = ["git"] + args
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
            "stdout": result.stdout[-10000:] if result.stdout else "",
            "stderr": result.stderr[-5000:] if result.stderr else "",
            "cmd": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "cmd": " ".join(cmd)}
    except Exception as e:
        return {"ok": False, "error": str(e), "cmd": " ".join(cmd)}


@function_tool
def git_status(cwd: str = ".") -> str:
    """
    Get Git repository status.

    Use cases:
    - Check for uncommitted changes before operations
    - See which files are staged/unstaged
    - Verify clean working directory

    Args:
        cwd: Directory to check (default: current directory)

    Returns:
        JSON with ok, branch, clean, and status info
    """
    logger.info("git_status", cwd=cwd)
    result = _run_git(["status", "--porcelain", "-b"], cwd=cwd or None)

    if result.get("ok"):
        lines = result.get("stdout", "").strip().split("\n")
        branch = ""
        if lines and lines[0].startswith("## "):
            branch_line = lines[0][3:]
            branch = (
                branch_line.split("...")[0] if "..." in branch_line else branch_line
            )
        clean = len(lines) <= 1 or (len(lines) == 1 and lines[0].startswith("##"))
        result["branch"] = branch
        result["clean"] = clean

    return json.dumps(result)


@function_tool
def git_diff(
    staged: bool = False, path: str = "", ref1: str = "", ref2: str = "", cwd: str = "."
) -> str:
    """
    Show changes between commits, working tree, etc.

    Use cases:
    - Review changes before commit
    - Compare branches
    - Check specific file changes

    Args:
        staged: Show staged changes only
        path: Specific file/directory to diff
        ref1: First reference (commit/branch)
        ref2: Second reference (commit/branch)
        cwd: Working directory

    Returns:
        JSON with ok and diff content
    """
    logger.info("git_diff", staged=staged, path=path)

    args = ["diff"]
    if staged:
        args.append("--staged")
    if ref1:
        args.append(ref1)
    if ref2:
        args.append(ref2)
    if path:
        args.extend(["--", path])

    result = _run_git(args, cwd=cwd or None)
    if result.get("ok"):
        result["diff"] = result.get("stdout", "")
    return json.dumps(result)


@function_tool
def git_log(
    limit: int = 10, oneline: bool = True, path: str = "", cwd: str = "."
) -> str:
    """
    Show commit history.

    Use cases:
    - Review recent commits
    - Find when a change was introduced
    - Check who made changes

    Args:
        limit: Number of commits to show (default 10)
        oneline: Compact format (default True)
        path: Filter by file path
        cwd: Working directory

    Returns:
        JSON with ok and commits list
    """
    logger.info("git_log", limit=limit, path=path)

    args = ["log", f"-{limit}"]
    if oneline:
        args.append("--oneline")
    else:
        args.extend(["--pretty=format:%H|%an|%ae|%s|%ci"])
    if path:
        args.extend(["--", path])

    result = _run_git(args, cwd=cwd or None)

    if result.get("ok"):
        lines = result.get("stdout", "").strip().split("\n")
        commits = []
        for line in lines:
            if line:
                if oneline:
                    parts = line.split(" ", 1)
                    commits.append(
                        {
                            "hash": parts[0],
                            "message": parts[1] if len(parts) > 1 else "",
                        }
                    )
                else:
                    parts = line.split("|")
                    if len(parts) >= 5:
                        commits.append(
                            {
                                "hash": parts[0],
                                "author": parts[1],
                                "email": parts[2],
                                "message": parts[3],
                                "date": parts[4],
                            }
                        )
        result["commits"] = commits

    return json.dumps(result)


@function_tool
def git_blame(path: str, cwd: str = ".") -> str:
    """
    Show what revision and author last modified each line of a file.

    Use cases:
    - Find who introduced a bug
    - Understand code history

    Args:
        path: File path to blame
        cwd: Working directory

    Returns:
        JSON with blame output
    """
    if not path:
        return json.dumps({"ok": False, "error": "path is required"})

    logger.info("git_blame", path=path)
    result = _run_git(["blame", "--line-porcelain", path], cwd=cwd or None)
    return json.dumps(result)


@function_tool
def git_show(ref: str = "HEAD", path: str = "", cwd: str = ".") -> str:
    """
    Show commit details or file contents at a specific revision.

    Use cases:
    - View commit details
    - See file at specific version

    Args:
        ref: Commit/branch reference (default HEAD)
        path: Optional file path
        cwd: Working directory

    Returns:
        JSON with show output
    """
    logger.info("git_show", ref=ref, path=path)

    args = ["show", ref]
    if path:
        args.append(f":{path}")

    result = _run_git(args, cwd=cwd or None)
    return json.dumps(result)


@function_tool
def git_branch_list(all_branches: bool = False, cwd: str = ".") -> str:
    """
    List branches in the repository.

    Args:
        all_branches: Include remote branches
        cwd: Working directory

    Returns:
        JSON with branches list and current branch
    """
    logger.info("git_branch_list", all_branches=all_branches)

    args = ["branch"]
    if all_branches:
        args.append("-a")

    result = _run_git(args, cwd=cwd or None)

    if result.get("ok"):
        branches = []
        current = ""
        for line in result.get("stdout", "").strip().split("\n"):
            line = line.strip()
            if line.startswith("* "):
                current = line[2:]
                branches.append(current)
            elif line:
                branches.append(line)
        result["branches"] = branches
        result["current"] = current

    return json.dumps(result)


@function_tool
def git_add(paths: str = ".", cwd: str = ".") -> str:
    """
    Stage files for commit.

    Use cases:
    - Stage changes before committing
    - Add new files to tracking
    - Stage specific files or directories

    Args:
        paths: Files/directories to add (default: "." for all changes)
        cwd: Working directory

    Returns:
        JSON with ok status and added files info
    """
    logger.info("git_add", paths=paths, cwd=cwd)

    args = ["add", paths]
    result = _run_git(args, cwd=cwd or None)

    # Get what was added by checking status
    if result.get("ok"):
        status_result = _run_git(["status", "--porcelain"], cwd=cwd or None)
        if status_result.get("ok"):
            staged = []
            for line in status_result.get("stdout", "").split("\n"):
                if line and (line.startswith("A ") or line.startswith("M ")):
                    staged.append(line[3:])
            result["staged_files"] = staged

    return json.dumps(result)


@function_tool
def git_commit(message: str, cwd: str = ".") -> str:
    """
    Create a commit with staged changes.

    Use cases:
    - Commit staged changes with a message
    - Create snapshots of work

    Args:
        message: Commit message
        cwd: Working directory

    Returns:
        JSON with ok status, commit hash, and files changed
    """
    if not message:
        return json.dumps({"ok": False, "error": "commit message is required"})

    logger.info("git_commit", message_preview=message[:50], cwd=cwd)

    args = ["commit", "-m", message]
    result = _run_git(args, cwd=cwd or None, timeout_s=120.0)

    # Extract commit hash from output if successful
    if result.get("ok"):
        # Try to get the commit hash
        log_result = _run_git(["rev-parse", "HEAD"], cwd=cwd or None)
        if log_result.get("ok"):
            result["commit_hash"] = log_result.get("stdout", "").strip()

        # Parse commit output for files changed
        stdout = result.get("stdout", "")
        if "files changed" in stdout or "file changed" in stdout:
            result["summary"] = stdout.strip()

    return json.dumps(result)


@function_tool
def git_push(
    remote: str = "origin", branch: str = "", force: bool = False, cwd: str = "."
) -> str:
    """
    Push commits to remote repository.

    Use cases:
    - Push local commits to remote
    - Sync changes with team
    - Deploy via git push

    Args:
        remote: Remote name (default: "origin")
        branch: Branch to push (empty = current branch)
        force: Force push (use with caution!)
        cwd: Working directory

    Returns:
        JSON with ok status and push result
    """
    logger.info("git_push", remote=remote, branch=branch, force=force, cwd=cwd)

    args = ["push", remote]
    if branch:
        args.append(branch)
    if force:
        args.append("--force")
        logger.warning("git_push_force_enabled", remote=remote, branch=branch)

    result = _run_git(args, cwd=cwd or None, timeout_s=180.0)

    # Parse output for success indicators
    if result.get("ok"):
        stdout = result.get("stdout", "") + result.get("stderr", "")
        if "Everything up-to-date" in stdout:
            result["status"] = "up_to_date"
        elif "->" in stdout:
            result["status"] = "pushed"

    return json.dumps(result)

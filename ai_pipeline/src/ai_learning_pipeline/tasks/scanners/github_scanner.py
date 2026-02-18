"""
GitHub Integration Scanner.

Scans a GitHub organization for operational knowledge:
- README files, runbooks, incident response docs
- CI/CD configs that reveal tooling

Calls the GitHub API directly using credentials fetched from config_service.
"""

import base64
import json
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import Document, register_scanner


def _log(event: str, **fields) -> None:
    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "ai-learning-pipeline",
        "module": "scanners.github",
        "event": event,
        **fields,
    }
    print(json.dumps(payload, default=str))


# Paths likely to contain operational knowledge
OPS_DOC_PATHS = [
    "README.md",
    "docs/runbook.md",
    "docs/runbooks/",
    "runbook.md",
    "RUNBOOK.md",
    "docs/oncall.md",
    "docs/on-call.md",
    "docs/incident-response.md",
    "docs/architecture.md",
    "docs/ops.md",
    ".github/INCIDENT_RESPONSE.md",
]

MAX_REPOS = 20
MAX_FILE_SIZE = 100_000  # 100KB


def _github_api(
    path: str,
    token: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Make a GitHub API request."""
    url = f"https://api.github.com{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "IncidentFox-Scanner")

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # Expected for missing files
        _log("github_api_error", path=path, status=e.code)
        return None
    except Exception as e:
        _log("github_api_failed", path=path, error=str(e))
        return None


def _list_repos(token: str, org: str) -> List[Dict[str, Any]]:
    """List repos for an org (or user if not an org)."""
    # Try org repos first
    repos = _github_api(f"/orgs/{org}/repos", token, {"per_page": 100, "sort": "pushed"})
    if repos is not None:
        return repos[:MAX_REPOS]

    # Fall back to user repos
    repos = _github_api(f"/users/{org}/repos", token, {"per_page": 100, "sort": "pushed"})
    return (repos or [])[:MAX_REPOS]


def _get_file_content(token: str, owner: str, repo: str, path: str) -> Optional[str]:
    """Fetch a file's decoded content from a repo."""
    data = _github_api(f"/repos/{owner}/{repo}/contents/{path}", token)
    if not data:
        return None

    # Handle directory listing (for paths ending in /)
    if isinstance(data, list):
        return None

    if data.get("size", 0) > MAX_FILE_SIZE:
        return None

    content_b64 = data.get("content", "")
    if not content_b64:
        return None

    try:
        return base64.b64decode(content_b64).decode("utf-8")
    except Exception:
        return None


@register_scanner("github")
async def scan(
    credentials: Dict[str, Any],
    config: Dict[str, Any],
    org_id: str,
) -> List[Document]:
    """
    Scan GitHub for operational documents.

    Args:
        credentials: Decrypted integration credentials (must contain api_key or token)
        config: Integration config (may contain default_org, account_login)
        org_id: IncidentFox org ID
    """
    token = credentials.get("api_key") or credentials.get("token", "")
    if not token:
        _log("no_github_token")
        return []

    github_org = config.get("account_login") or config.get("default_org") or config.get("org", "")
    if not github_org:
        _log("no_github_org")
        return []

    _log("github_scan_started", org=github_org)

    repos = _list_repos(token, github_org)
    if not repos:
        _log("no_repos_found", org=github_org)
        return []

    documents: List[Document] = []

    for repo_data in repos:
        repo_name = repo_data.get("name", "")
        full_name = repo_data.get("full_name", f"{github_org}/{repo_name}")
        owner = full_name.split("/")[0] if "/" in full_name else github_org

        for doc_path in OPS_DOC_PATHS:
            content = _get_file_content(token, owner, repo_name, doc_path)
            if content and len(content) >= 50:
                documents.append(
                    Document(
                        content=content,
                        source_url=f"https://github.com/{full_name}/blob/main/{doc_path}",
                        content_type="markdown",
                        metadata={
                            "repo": full_name,
                            "path": doc_path,
                            "org_id": org_id,
                            "source": "integration_scan",
                        },
                    )
                )

    _log("github_scan_completed", repos_scanned=len(repos), documents_found=len(documents))
    return documents

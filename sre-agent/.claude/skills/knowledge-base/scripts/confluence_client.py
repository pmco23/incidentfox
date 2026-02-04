"""Shared Confluence API client with credential proxy support.

This client is designed to work with the IncidentFox credential proxy.
Credentials are injected automatically - scripts should NOT check for
CONFLUENCE_API_TOKEN in environment variables.
"""

import json
import os
from pathlib import Path
from typing import Any


def get_config() -> dict[str, Any]:
    """Load configuration from standard locations."""
    config = {}

    # Check for config file
    config_paths = [
        Path.home() / ".incidentfox" / "config.json",
        Path("/etc/incidentfox/config.json"),
    ]

    for path in config_paths:
        if path.exists():
            with open(path) as f:
                config = json.load(f)
                break

    # Environment overrides
    if os.getenv("TENANT_ID"):
        config["tenant_id"] = os.getenv("TENANT_ID")
    if os.getenv("TEAM_ID"):
        config["team_id"] = os.getenv("TEAM_ID")

    return config


def get_confluence_client():
    """Get Confluence client instance.

    Returns:
        Confluence client instance

    Raises:
        RuntimeError: If configuration is missing
    """
    try:
        from atlassian import Confluence
    except ImportError:
        raise RuntimeError(
            "atlassian-python-api not installed. Run: uv pip install atlassian-python-api"
        )

    # Try environment variables (local development)
    url = os.getenv("CONFLUENCE_URL")
    email = os.getenv("CONFLUENCE_EMAIL")
    api_token = os.getenv("CONFLUENCE_API_TOKEN")

    if not url:
        raise RuntimeError(
            "No Confluence URL configured. Set CONFLUENCE_URL environment variable."
        )

    if not email or not api_token:
        raise RuntimeError(
            "No Confluence credentials configured. Set CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN."
        )

    # Remove trailing slash and /wiki if present
    url = url.rstrip("/")
    if url.endswith("/wiki"):
        url = url[:-5]

    return Confluence(
        url=url,
        username=email,
        password=api_token,
        cloud=True,
    )


def search_content(
    cql: str,
    limit: int = 25,
    expand: str | None = None,
) -> dict[str, Any]:
    """Search Confluence using CQL (Confluence Query Language).

    Args:
        cql: CQL query string
        limit: Maximum results to return
        expand: Optional fields to expand

    Returns:
        Search results
    """
    confluence = get_confluence_client()
    return confluence.cql(cql, limit=limit, expand=expand)


def get_page_by_id(
    page_id: str,
    expand: str = "body.storage,version,space",
) -> dict[str, Any]:
    """Get a Confluence page by ID.

    Args:
        page_id: Page ID
        expand: Fields to expand

    Returns:
        Page data
    """
    confluence = get_confluence_client()
    return confluence.get_page_by_id(page_id, expand=expand)


def get_page_by_title(
    space: str,
    title: str,
    expand: str = "body.storage,version,space",
) -> dict[str, Any]:
    """Get a Confluence page by title.

    Args:
        space: Space key
        title: Page title
        expand: Fields to expand

    Returns:
        Page data
    """
    confluence = get_confluence_client()
    return confluence.get_page_by_title(space=space, title=title, expand=expand)


def format_page_result(result: dict[str, Any]) -> dict[str, Any]:
    """Format a CQL search result for consistent output.

    Args:
        result: Raw result from CQL search

    Returns:
        Formatted page data
    """
    content = result.get("content", {})

    return {
        "id": content.get("id"),
        "title": content.get("title"),
        "type": content.get("type"),
        "space": content.get("space", {}).get("key") if content.get("space") else None,
        "url": result.get("url"),
        "excerpt": result.get("excerpt", ""),
        "created": content.get("history", {}).get("createdDate"),
        "updated": result.get("lastModified"),
    }

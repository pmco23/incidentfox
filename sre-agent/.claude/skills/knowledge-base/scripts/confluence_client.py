"""Shared Confluence API client with credential proxy support.

This client is designed to work with the IncidentFox credential proxy.
Credentials are injected automatically - scripts should NOT check for
CONFLUENCE_API_TOKEN in environment variables.
"""

import json
import os
from pathlib import Path
from typing import Any

import httpx


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


def get_api_url(endpoint: str) -> str:
    """Get the Confluence API URL for an endpoint.

    In production, this routes through the credential proxy.
    """
    base_url = os.getenv("CONFLUENCE_BASE_URL")
    if not base_url:
        # Fall back to direct API (for local development only)
        confluence_url = os.getenv("CONFLUENCE_URL", "").rstrip("/")
        if confluence_url:
            base_url = f"{confluence_url}/wiki/api/v2"
        else:
            raise RuntimeError(
                "No Confluence URL configured. Set CONFLUENCE_BASE_URL or CONFLUENCE_URL."
            )

    return f"{base_url.rstrip('/')}{endpoint}"


def get_headers() -> dict[str, str]:
    """Get headers for Confluence API requests.

    The credential proxy will inject Authorization header.
    """
    config = get_config()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Tenant-Id": config.get("tenant_id") or "local",
        "X-Team-Id": config.get("team_id") or "local",
    }

    # For local development, allow direct token usage
    api_token = os.getenv("CONFLUENCE_API_TOKEN")
    email = os.getenv("CONFLUENCE_EMAIL")
    if api_token and email and not os.getenv("CONFLUENCE_BASE_URL"):
        # Use basic auth for direct API access
        import base64

        auth_string = f"{email}:{api_token}"
        b64_auth = base64.b64encode(auth_string.encode()).decode()
        headers["Authorization"] = f"Basic {b64_auth}"

    return headers


def api_request(
    method: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a request to the Confluence API.

    Args:
        method: HTTP method
        endpoint: API endpoint (e.g., "/search")
        params: Query parameters
        json_data: JSON body

    Returns:
        Parsed JSON response

    Raises:
        RuntimeError: If the request fails
    """
    url = get_api_url(endpoint)
    headers = get_headers()

    with httpx.Client(timeout=60.0) as client:
        response = client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Confluence API error: {response.status_code} - {response.text}"
            )

        return response.json()


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
    params = {
        "cql": cql,
        "limit": limit,
    }

    if expand:
        params["expand"] = expand

    return api_request("GET", "/search", params=params)


def get_page_by_id(
    page_id: str,
    body_format: str = "storage",
) -> dict[str, Any]:
    """Get a Confluence page by ID.

    Args:
        page_id: Page ID
        body_format: Body format (storage, view, atlas_doc_format)

    Returns:
        Page data
    """
    params = {
        "body-format": body_format,
    }

    return api_request("GET", f"/pages/{page_id}", params=params)


def format_page_result(page: dict[str, Any]) -> dict[str, Any]:
    """Format a page result for consistent output.

    Args:
        page: Raw page data from API

    Returns:
        Formatted page data
    """
    return {
        "id": page.get("id"),
        "title": page.get("title"),
        "type": page.get("type"),
        "space": page.get("spaceId"),
        "url": page.get("_links", {}).get("webui"),
        "created": page.get("createdAt"),
        "updated": page.get("lastUpdated"),
    }

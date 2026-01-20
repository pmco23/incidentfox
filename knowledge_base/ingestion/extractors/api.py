"""API-based extractors for various services."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

from ingestion.extractors.base import BaseExtractor
from ingestion.metadata import ExtractedContent, SourceMetadata


class APIExtractor(BaseExtractor):
    """Extract content from REST/GraphQL APIs."""

    def __init__(
        self,
        api_type: Optional[str] = None,
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        auth_token: Optional[str] = None,
    ):
        """
        Initialize API extractor.

        Args:
            api_type: Type of API ("github", "slack", "confluence", "custom")
            base_url: Base URL for API
            headers: Custom headers
            auth_token: Authentication token
        """
        self.api_type = api_type or "custom"
        self.base_url = base_url
        self.headers = headers or {}
        if auth_token:
            if self.api_type == "github":
                self.headers["Authorization"] = f"token {auth_token}"
            else:
                self.headers["Authorization"] = f"Bearer {auth_token}"

    def can_handle(self, source: str) -> bool:
        """Check if source looks like an API endpoint."""
        # Check if it's a URL that might be an API
        try:
            parsed = urlparse(source)
            # Could be API if it has /api/ in path or ends with .json
            return parsed.scheme in ("http", "https") and (
                "/api/" in parsed.path or source.endswith(".json")
            )
        except Exception:
            return False

    def extract(self, source: str, **kwargs) -> ExtractedContent:
        """Extract content from API endpoint."""
        start_time = time.time()

        # Build full URL
        if self.base_url and not source.startswith("http"):
            url = f"{self.base_url.rstrip('/')}/{source.lstrip('/')}"
        else:
            url = source

        source_id = hashlib.sha1(url.encode()).hexdigest()
        metadata = SourceMetadata(
            source_type=f"api_{self.api_type}",
            source_url=url,
            source_id=source_id,
            ingested_at=datetime.utcnow(),
            original_format="json",
            mime_type="application/json",
            extraction_method="api_call",
        )

        # Make API call
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()

        # Parse response
        try:
            data = response.json()
            text = self._format_api_response(data, self.api_type)
        except ValueError:
            # Not JSON, treat as text
            text = response.text

        duration = time.time() - start_time
        metadata.processing_duration_seconds = duration
        metadata.processing_steps.append("api_extraction")
        metadata.custom_metadata["status_code"] = response.status_code

        return ExtractedContent(
            text=text,
            metadata=metadata,
        )

    def _format_api_response(self, data: Any, api_type: str) -> str:
        """Format API response as readable text."""
        if api_type == "github":
            return self._format_github_response(data)
        elif api_type == "slack":
            return self._format_slack_response(data)
        else:
            # Generic JSON formatting
            return json.dumps(data, indent=2)

    def _format_github_response(self, data: Dict) -> str:
        """Format GitHub API response."""
        parts = []
        if isinstance(data, dict):
            if "title" in data:
                parts.append(f"# {data['title']}")
            if "body" in data:
                parts.append(data["body"])
            if "content" in data:
                # Decode base64 if needed
                import base64

                try:
                    content = base64.b64decode(data["content"]).decode("utf-8")
                    parts.append(content)
                except Exception:
                    pass
            # Fallback: format as JSON
            if not parts:
                parts.append(json.dumps(data, indent=2))
        return "\n\n".join(parts)

    def _format_slack_response(self, data: Dict) -> str:
        """Format Slack API response."""
        parts = []
        if isinstance(data, dict):
            if "messages" in data:
                for msg in data["messages"]:
                    if "text" in msg:
                        parts.append(f"**{msg.get('user', 'Unknown')}**: {msg['text']}")
            # Fallback
            if not parts:
                parts.append(json.dumps(data, indent=2))
        return "\n\n".join(parts)


class GitHubExtractor(APIExtractor):
    """Extract content from GitHub repositories."""

    def __init__(self, auth_token: Optional[str] = None):
        """Initialize GitHub extractor."""
        super().__init__(
            api_type="github",
            base_url="https://api.github.com",
            auth_token=auth_token,
        )

    def extract_repo_file(self, owner: str, repo: str, path: str) -> ExtractedContent:
        """Extract a specific file from a GitHub repository."""
        url = f"repos/{owner}/{repo}/contents/{path}"
        return self.extract(url)

    def extract_repo_readme(self, owner: str, repo: str) -> ExtractedContent:
        """Extract README from a GitHub repository."""
        return self.extract_repo_file(owner, repo, "README.md")


class SlackExtractor(APIExtractor):
    """Extract content from Slack channels."""

    def __init__(self, auth_token: str):
        """Initialize Slack extractor."""
        super().__init__(
            api_type="slack",
            base_url="https://slack.com/api",
            auth_token=auth_token,
        )

    def extract_channel_history(
        self, channel_id: str, limit: int = 100
    ) -> ExtractedContent:
        """Extract message history from a Slack channel."""
        url = f"conversations.history?channel={channel_id}&limit={limit}"
        return self.extract(url)

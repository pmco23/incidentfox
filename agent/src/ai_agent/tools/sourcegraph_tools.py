"""Sourcegraph code search tools."""

import os
from typing import Any

import httpx

from ..core.errors import ToolExecutionError
from ..core.logging import get_logger
from ..core.metrics import track_tool_metrics

logger = get_logger(__name__)


@track_tool_metrics("sourcegraph_search")
def search_sourcegraph(
    query: str,
    repo_filter: str | None = None,
    file_filter: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Search code across all repositories in Sourcegraph.

    Args:
        query: Search query
        repo_filter: Optional repo filter (e.g., 'github.com/org/*')
        file_filter: Optional file pattern (e.g., '*.py')
        limit: Max results

    Returns:
        List of code matches
    """
    try:
        url = os.getenv("SOURCEGRAPH_URL", "https://sourcegraph.com")
        token = os.getenv("SOURCEGRAPH_TOKEN")

        if not token:
            raise ValueError("SOURCEGRAPH_TOKEN not set")

        # Build search query
        search_query = query
        if repo_filter:
            search_query += f" repo:{repo_filter}"
        if file_filter:
            search_query += f" file:{file_filter}"

        # GraphQL query
        graphql_query = """
        query Search($query: String!) {
            search(query: $query) {
                results {
                    results {
                        ... on FileMatch {
                            file {
                                path
                                url
                                repository {
                                    name
                                }
                            }
                            lineMatches {
                                lineNumber
                                line
                            }
                        }
                    }
                }
            }
        }
        """

        with httpx.Client() as client:
            response = client.post(
                f"{url}/.api/graphql",
                headers={"Authorization": f"token {token}"},
                json={"query": graphql_query, "variables": {"query": search_query}},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        matches = []
        for result in (
            data.get("data", {}).get("search", {}).get("results", {}).get("results", [])
        ):
            if len(matches) >= limit:
                break

            matches.append(
                {
                    "file_path": result["file"]["path"],
                    "repository": result["file"]["repository"]["name"],
                    "url": result["file"]["url"],
                    "matches": [
                        {"line": m["lineNumber"], "content": m["line"]}
                        for m in result.get("lineMatches", [])[:3]
                    ],
                }
            )

        logger.info("sourcegraph_search_completed", query=query, results=len(matches))
        return matches

    except Exception as e:
        logger.error("sourcegraph_search_failed", error=str(e), query=query)
        raise ToolExecutionError("search_sourcegraph", str(e), e)

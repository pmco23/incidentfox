"""
Knowledge Base tools for RAPTOR tree-organized retrieval.

These tools allow agents to query the team's knowledge base
for relevant runbooks, documentation, and past incident learnings.
"""

from __future__ import annotations

import json
import os

from agents import function_tool

from ..core.logging import get_logger

logger = get_logger(__name__)

# Configuration
RAPTOR_URL = os.getenv("RAPTOR_URL", "http://localhost:8000")
DEFAULT_TREE = os.getenv("RAPTOR_DEFAULT_TREE", "k8s")


def _get_raptor_client():
    """Get HTTP client for RAPTOR API."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx not installed")

    return httpx.Client(base_url=RAPTOR_URL, timeout=30.0)


@function_tool
def search_knowledge_base(query: str, tree: str = "", top_k: int = 5) -> str:
    """
    Search the knowledge base for relevant information.

    Uses RAPTOR tree-organized retrieval to find relevant:
    - Runbooks and procedures
    - Past incident resolutions
    - System documentation
    - Kubernetes/AWS best practices

    The knowledge base is organized hierarchically:
    - Leaf nodes: Original document chunks
    - Parent nodes: AI-generated summaries of related content

    Use cases:
    - "How do I debug OOMKilled pods?"
    - "What's the procedure for database failover?"
    - "Find runbooks for the affected service"

    Args:
        query: Natural language search query
        tree: Knowledge tree to search (default: k8s). Options: k8s, runbooks, incidents
        top_k: Number of results to return (default: 5)

    Returns:
        JSON with relevant knowledge chunks, scores, and context
    """
    try:
        with _get_raptor_client() as client:
            response = client.post(
                "/api/v1/search",
                json={
                    "query": query,
                    "tree": tree or DEFAULT_TREE,
                    "top_k": top_k,
                    "include_summaries": True,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Format results for agent consumption
            results = []
            for r in data.get("results", []):
                results.append(
                    {
                        "text": r.get("text", ""),
                        "relevance": r.get("score", 0),
                        "is_summary": r.get("is_summary", False),
                        "layer": r.get("layer", 0),
                    }
                )

            logger.info("knowledge_base_search", query=query[:50], results=len(results))

            return json.dumps(
                {
                    "ok": True,
                    "query": query,
                    "tree": data.get("tree", tree or DEFAULT_TREE),
                    "results": results,
                    "total_results": len(results),
                }
            )

    except Exception as e:
        logger.error("knowledge_base_search_failed", error=str(e))
        return json.dumps(
            {
                "ok": False,
                "error": str(e),
                "hint": "Knowledge base may not be available. Continue investigation with other tools.",
            }
        )


@function_tool
def ask_knowledge_base(question: str, tree: str = "", top_k: int = 5) -> str:
    """
    Ask a question and get a direct answer from the knowledge base.

    Unlike search_knowledge_base which returns chunks, this tool:
    1. Retrieves relevant context from the RAPTOR tree
    2. Uses an LLM to synthesize an answer
    3. Returns a concise answer with supporting evidence

    Best for:
    - Direct questions: "What causes OOMKilled?"
    - Procedural questions: "How do I restart a service?"
    - Lookup questions: "What's the oncall escalation path?"

    Args:
        question: Natural language question
        tree: Knowledge tree to query (default: k8s)
        top_k: Number of context chunks to use

    Returns:
        JSON with answer and supporting context
    """
    try:
        with _get_raptor_client() as client:
            response = client.post(
                "/api/v1/answer",
                json={
                    "question": question,
                    "tree": tree or DEFAULT_TREE,
                    "top_k": top_k,
                },
            )
            response.raise_for_status()
            data = response.json()

            logger.info("knowledge_base_answer", question=question[:50])

            # Include citations if available (new feature)
            citations = data.get("citations", [])
            citation_sources = [
                c.get("source", "") for c in citations if c.get("source")
            ]

            return json.dumps(
                {
                    "ok": True,
                    "question": question,
                    "answer": data.get("answer", ""),
                    "tree": data.get("tree", tree or DEFAULT_TREE),
                    "context_snippets": data.get("context_chunks", [])[
                        :3
                    ],  # First 3 for brevity
                    "sources": (
                        citation_sources[:5] if citation_sources else []
                    ),  # Top 5 sources
                }
            )

    except Exception as e:
        logger.error("knowledge_base_answer_failed", error=str(e))
        return json.dumps(
            {
                "ok": False,
                "error": str(e),
                "hint": "Knowledge base may not be available. Try web_search or llm_call instead.",
            }
        )


@function_tool
def get_knowledge_context(topic: str, tree: str = "", max_chunks: int = 10) -> str:
    """
    Get contextual knowledge for a topic (for augmenting investigation).

    Returns raw chunks that can be used to augment your investigation.
    Unlike ask_knowledge_base, this doesn't generate an answer -
    it just retrieves relevant background knowledge.

    Use cases:
    - Get background on a service before investigating
    - Understand typical architecture patterns
    - Find related past incidents

    Args:
        topic: Topic to get context for
        tree: Knowledge tree (default: k8s)
        max_chunks: Maximum chunks to return

    Returns:
        JSON with knowledge chunks for context
    """
    try:
        with _get_raptor_client() as client:
            response = client.post(
                "/api/v1/retrieve",
                json={
                    "query": topic,
                    "tree": tree or DEFAULT_TREE,
                    "top_k": max_chunks,
                    "collapse_tree": True,
                },
            )
            response.raise_for_status()
            data = response.json()

            chunks = data.get("chunks", [])

            # Combine into context string
            context_parts = []
            for i, chunk in enumerate(chunks[:max_chunks]):
                layer_info = (
                    f"[L{chunk.get('layer', 0)}]" if chunk.get("is_summary") else ""
                )
                context_parts.append(
                    f"--- Chunk {i+1} {layer_info} ---\n{chunk.get('text', '')[:1000]}"
                )

            context = "\n\n".join(context_parts)

            logger.info(
                "knowledge_context_retrieved", topic=topic[:50], chunks=len(chunks)
            )

            return json.dumps(
                {
                    "ok": True,
                    "topic": topic,
                    "tree": data.get("tree", tree or DEFAULT_TREE),
                    "chunks_retrieved": len(chunks),
                    "context": context,
                }
            )

    except Exception as e:
        logger.error("knowledge_context_failed", error=str(e))
        return json.dumps(
            {
                "ok": False,
                "error": str(e),
            }
        )


@function_tool
def list_knowledge_trees() -> str:
    """
    List available knowledge trees.

    Different trees contain different types of knowledge:
    - k8s: Kubernetes documentation and best practices
    - runbooks: Team-specific runbooks and procedures
    - incidents: Past incident learnings and resolutions
    - aws: AWS documentation and patterns

    Returns:
        JSON with available trees
    """
    try:
        with _get_raptor_client() as client:
            response = client.get("/api/v1/trees")
            response.raise_for_status()
            data = response.json()

            return json.dumps(
                {
                    "ok": True,
                    "trees": data.get("trees", []),
                    "default": data.get("default", DEFAULT_TREE),
                    "loaded": data.get("loaded", []),
                }
            )

    except Exception as e:
        logger.error("list_trees_failed", error=str(e))
        return json.dumps(
            {
                "ok": False,
                "error": str(e),
                "available_trees": ["k8s"],  # Fallback
            }
        )

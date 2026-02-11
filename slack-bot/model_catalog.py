"""
Dynamic model catalog for LLM provider selection.

Fetches available models from OpenRouter's API (uses OPENROUTER_API_KEY if set)
and caches them. Provides filtered model lists for Slack modal dropdowns.
"""

import logging
import threading
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Cache TTL: 1 hour
_CACHE_TTL = 3600

# Map our LLM_PROVIDERS provider IDs to OpenRouter model prefixes.
# Our provider_id -> list of OpenRouter prefixes that belong to it.
_PROVIDER_PREFIX_MAP = {
    "anthropic": ["anthropic"],
    "openai": ["openai"],
    "gemini": ["google"],
    "deepseek": ["deepseek"],
    "xai": ["x-ai"],
    "mistral": ["mistralai"],
    "cohere": ["cohere"],
    "together_ai": ["meta-llama", "nousresearch", "nvidia"],
    "groq": [],  # Groq hosts models from other providers, not on OpenRouter
    "moonshot": ["moonshotai"],
    "minimax": ["minimax"],
    # OpenRouter itself shows all models
    "openrouter": [],  # Special case: show all models
}


class ModelCatalog:
    """Cached model catalog backed by OpenRouter's public API."""

    def __init__(self):
        self._models: List[Dict] = []
        self._last_fetch: float = 0
        self._lock = threading.Lock()

    def _fetch_models(self) -> List[Dict]:
        """Fetch models from OpenRouter (uses OPENROUTER_API_KEY if available)."""
        try:
            import json
            import os
            import urllib.request

            headers = {"User-Agent": "IncidentFox/1.0"}
            api_key = os.getenv("OPENROUTER_API_KEY", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                models = data.get("data", [])
                logger.info(f"Fetched {len(models)} models from OpenRouter")
                return models
        except Exception as e:
            logger.warning(f"Failed to fetch models from OpenRouter: {e}")
            return []

    def _ensure_cache(self):
        """Refresh cache if stale."""
        now = time.time()
        if now - self._last_fetch > _CACHE_TTL:
            with self._lock:
                # Double-check after acquiring lock
                if time.time() - self._last_fetch > _CACHE_TTL:
                    self._models = self._fetch_models()
                    self._last_fetch = time.time()

    def get_models_for_provider(
        self,
        provider_id: str,
        query: str = "",
        limit: int = 100,
    ) -> List[Dict]:
        """
        Get models for a specific provider, optionally filtered by search query.

        Returns list of dicts with 'id' (model ID in our format) and 'name' (display name).
        """
        self._ensure_cache()

        if provider_id == "openrouter":
            # For OpenRouter, show ALL models (it's a meta-provider)
            candidates = self._models
        else:
            # Filter by provider prefix
            prefixes = _PROVIDER_PREFIX_MAP.get(provider_id, [])
            if not prefixes:
                return []

            candidates = [
                m
                for m in self._models
                if any(m.get("id", "").startswith(p + "/") for p in prefixes)
            ]

        if not candidates:
            return []

        # Convert to our format and filter by query
        results = []
        for m in candidates:
            or_id = m.get("id", "")
            name = m.get("name", or_id)

            # Convert OpenRouter model ID to our LiteLLM format
            model_id = self._to_litellm_id(or_id, provider_id)

            if query:
                q = query.lower()
                if q not in model_id.lower() and q not in name.lower():
                    continue

            results.append({"id": model_id, "name": name})

        # Sort by name
        results.sort(key=lambda m: m["name"])
        return results[:limit]

    def _to_litellm_id(self, openrouter_id: str, provider_id: str) -> str:
        """
        Convert an OpenRouter model ID to our LiteLLM-compatible format.

        OpenRouter: anthropic/claude-sonnet-4.5 -> claude-sonnet-4-20250514 (for anthropic)
        OpenRouter: openai/gpt-5 -> openai/gpt-5 (for openai)
        OpenRouter: google/gemini-2.5-flash -> gemini/gemini-2.5-flash (for gemini)
        """
        if provider_id == "openrouter":
            # For OpenRouter provider, prefix with openrouter/
            return f"openrouter/{openrouter_id}"

        if provider_id == "anthropic":
            # Anthropic models don't use provider prefix in LiteLLM
            # anthropic/claude-sonnet-4.5 -> claude-sonnet-4.5
            return (
                openrouter_id.split("/", 1)[-1]
                if "/" in openrouter_id
                else openrouter_id
            )

        # Map OpenRouter prefix -> our LiteLLM prefix
        prefix_map = {
            "google": "gemini",
            "x-ai": "xai",
            "mistralai": "mistral",
            "moonshotai": "moonshot",
        }

        parts = openrouter_id.split("/", 1)
        if len(parts) == 2:
            or_prefix, model_name = parts
            our_prefix = prefix_map.get(or_prefix, or_prefix)
            return f"{our_prefix}/{model_name}"

        return openrouter_id


# Singleton instance
_catalog = ModelCatalog()


def get_models_for_provider(
    provider_id: str, query: str = "", limit: int = 100
) -> List[Dict]:
    """Get models for a provider. Uses cached OpenRouter data."""
    return _catalog.get_models_for_provider(provider_id, query, limit)

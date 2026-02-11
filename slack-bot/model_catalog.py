"""
Dynamic model catalog for LLM provider selection.

Fetches models from each provider's native API (using server-side keys) for accurate
model IDs, then enriches with descriptions from OpenRouter. Falls back to OpenRouter
for providers where we don't have a native API key.
"""

import json
import logging
import os
import threading
import time
import urllib.request
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Cache TTL: 1 hour
_CACHE_TTL = 3600

# --- Provider native API configuration ---
# Each entry: (models_endpoint, auth_style, env_var)
# auth_style: "bearer" = Authorization: Bearer <key>, "query" = ?key=<key> param
_NATIVE_API_CONFIG = {
    "openai": ("https://api.openai.com/v1/models", "bearer", "OPENAI_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models", "query", "GEMINI_API_KEY"),
    "deepseek": ("https://api.deepseek.com/v1/models", "bearer", "DEEPSEEK_API_KEY"),
    "xai": ("https://api.x.ai/v1/models", "bearer", "XAI_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1/models", "bearer", "MISTRAL_API_KEY"),
    "moonshot": ("https://api.moonshot.ai/v1/models", "bearer", "MOONSHOT_API_KEY"),
}

# OpenRouter prefix map — used for fallback + description enrichment
_OR_PREFIX_MAP = {
    "anthropic": ["anthropic"],
    "openai": ["openai"],
    "gemini": ["google"],
    "deepseek": ["deepseek"],
    "xai": ["x-ai"],
    "mistral": ["mistralai"],
    "cohere": ["cohere"],
    "qwen": ["qwen"],
    "moonshot": ["moonshotai"],
    "minimax": ["minimax"],
}

# LiteLLM prefix for each provider (how model IDs are formatted for LiteLLM)
_LITELLM_PREFIX = {
    "anthropic": "",  # No prefix: claude-sonnet-4.5
    "openai": "openai",
    "gemini": "gemini",
    "deepseek": "deepseek",
    "xai": "xai",
    "mistral": "mistral",
    "cohere": "cohere",
    "qwen": "qwen",
    "moonshot": "moonshot",
    "minimax": "minimax",
}

# Models to exclude from OpenAI (non-chat: image gen, TTS, STT, embeddings, etc.)
_OPENAI_SKIP_KEYWORDS = frozenset([
    "dall-e", "tts", "whisper", "embedding", "realtime", "audio",
    "transcribe", "moderation", "sora", "image", "search",
    "computer-use", "babbage", "davinci", "instruct",
])
# Note: "codex" not in skip list — gpt-5-codex, gpt-5.2-codex are chat-capable.
# Standalone codex-* models (e.g. codex-mini-latest) are excluded by the
# include-prefix check (only gpt-*/o1*/o3*/o4*/chatgpt-* pass through).


def _fetch_json(url: str, headers: dict, timeout: int = 10) -> dict:
    """Fetch JSON from URL."""
    req = urllib.request.Request(url, headers={**headers, "User-Agent": "IncidentFox/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())

class ModelCatalog:
    """Cached model catalog with native API fetching + OpenRouter enrichment."""

    def __init__(self):
        self._native_cache: Dict[str, List[Dict]] = {}  # provider_id -> models
        self._or_cache: List[Dict] = []  # Raw OpenRouter models
        self._or_descriptions: Dict[str, str] = {}  # native_model_id -> description
        self._last_fetch: Dict[str, float] = {}  # provider_id -> timestamp
        self._or_last_fetch: float = 0
        self._lock = threading.Lock()

    # --- OpenRouter (descriptions + fallback) ---

    def _fetch_openrouter(self) -> List[Dict]:
        """Fetch all models from OpenRouter for descriptions and fallback."""
        try:
            headers = {}
            api_key = os.getenv("OPENROUTER_API_KEY", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            data = _fetch_json("https://openrouter.ai/api/v1/models", headers)
            models = data.get("data", [])
            logger.info(f"Fetched {len(models)} models from OpenRouter")
            return models
        except Exception as e:
            logger.warning(f"Failed to fetch OpenRouter models: {e}")
            return []

    def _ensure_or_cache(self):
        """Refresh OpenRouter cache if stale."""
        now = time.time()
        if now - self._or_last_fetch > _CACHE_TTL:
            with self._lock:
                if time.time() - self._or_last_fetch > _CACHE_TTL:
                    self._or_cache = self._fetch_openrouter()
                    # Build description lookup: strip provider prefix -> description
                    self._or_descriptions = {}
                    for m in self._or_cache:
                        or_id = m.get("id", "")
                        desc = m.get("description", "")
                        if desc and "/" in or_id:
                            raw = or_id.split("/", 1)[1]
                            self._or_descriptions[raw] = desc
                    self._or_last_fetch = time.time()

    # --- Native API fetching ---

    def _fetch_native_openai(self, api_key: str) -> List[Dict]:
        """Fetch chat models from OpenAI's native API."""
        data = _fetch_json(
            "https://api.openai.com/v1/models",
            {"Authorization": f"Bearer {api_key}"},
        )
        results = []
        for m in data.get("data", []):
            mid = m["id"]
            # Only include chat-capable models
            if not any(mid.startswith(p) for p in ("gpt-", "o1", "o3", "o4", "chatgpt-")):
                continue
            if any(kw in mid for kw in _OPENAI_SKIP_KEYWORDS):
                continue
            results.append({"id": mid, "name": mid, "created": m.get("created", 0)})
        return results

    def _fetch_native_gemini(self, api_key: str) -> List[Dict]:
        """Fetch chat models from Google's Gemini API."""
        data = _fetch_json(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            {},
        )
        results = []
        for m in data.get("models", []):
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            mid = m["name"].replace("models/", "")
            # Skip image/TTS models
            if any(kw in mid for kw in ("image", "tts", "robotics")):
                continue
            results.append({
                "id": mid,
                "name": m.get("displayName", mid),
                "created": 0,  # Gemini API doesn't provide timestamps
            })
        return results

    def _fetch_native_openai_compat(self, endpoint: str, api_key: str) -> List[Dict]:
        """Fetch models from an OpenAI-compatible API (DeepSeek, Mistral, xAI, etc.)."""
        data = _fetch_json(endpoint, {"Authorization": f"Bearer {api_key}"})
        results = []
        for m in data.get("data", []):
            mid = m["id"]
            # Skip embedding models
            if "embed" in mid:
                continue
            results.append({"id": mid, "name": mid, "created": m.get("created", 0)})
        return results

    def _fetch_native(self, provider_id: str) -> Optional[List[Dict]]:
        """Fetch models from a provider's native API. Returns None if no config/key."""
        config = _NATIVE_API_CONFIG.get(provider_id)
        if not config:
            return None

        endpoint, auth_style, env_var = config
        api_key = os.getenv(env_var, "")
        if not api_key:
            return None

        try:
            if provider_id == "openai":
                return self._fetch_native_openai(api_key)
            elif provider_id == "gemini":
                return self._fetch_native_gemini(api_key)
            else:
                return self._fetch_native_openai_compat(endpoint, api_key)
        except Exception as e:
            logger.warning(f"Failed to fetch native models for {provider_id}: {e}")
            return None

    def _ensure_provider_cache(self, provider_id: str):
        """Refresh provider cache if stale."""
        now = time.time()
        last = self._last_fetch.get(provider_id, 0)
        if now - last > _CACHE_TTL:
            with self._lock:
                if time.time() - self._last_fetch.get(provider_id, 0) > _CACHE_TTL:
                    models = self._fetch_native(provider_id)
                    if models is not None:
                        self._native_cache[provider_id] = models
                        logger.info(f"Fetched {len(models)} native models for {provider_id}")
                    self._last_fetch[provider_id] = time.time()

    # --- Public API ---

    def get_models_for_provider(
        self,
        provider_id: str,
        query: str = "",
        limit: int = 100,
    ) -> List[Dict]:
        """Get models for a provider with descriptions, filtered by optional query."""
        # Always load OpenRouter for descriptions
        self._ensure_or_cache()

        # OpenRouter provider: show all OpenRouter models
        if provider_id == "openrouter":
            return self._get_openrouter_models(query, limit)

        # Try native API first
        self._ensure_provider_cache(provider_id)
        native_models = self._native_cache.get(provider_id)

        if native_models is not None:
            return self._format_native(provider_id, native_models, query, limit)

        # Fallback: filter OpenRouter models
        return self._get_from_openrouter(provider_id, query, limit)

    def _format_native(
        self, provider_id: str, models: List[Dict], query: str, limit: int,
    ) -> List[Dict]:
        """Format native models with LiteLLM prefix and OpenRouter descriptions."""
        prefix = _LITELLM_PREFIX.get(provider_id, provider_id)
        results = []
        for m in models:
            raw_id = m["id"]
            # Build LiteLLM model ID
            litellm_id = f"{prefix}/{raw_id}" if prefix else raw_id
            name = m.get("name", raw_id)

            if query:
                q = query.lower()
                if q not in raw_id.lower() and q not in name.lower():
                    continue

            # Enrich with OpenRouter description
            description = self._or_descriptions.get(raw_id, "")

            results.append({
                "id": litellm_id,
                "name": name,
                "created": m.get("created", 0),
                "description": description,
            })

        results.sort(key=lambda m: m.get("created", 0), reverse=True)
        return results[:limit]

    def _get_from_openrouter(
        self, provider_id: str, query: str, limit: int,
    ) -> List[Dict]:
        """Fallback: get models from OpenRouter for providers without native API."""
        prefixes = _OR_PREFIX_MAP.get(provider_id, [])
        if not prefixes:
            return []

        candidates = [
            m for m in self._or_cache
            if any(m.get("id", "").startswith(p + "/") for p in prefixes)
        ]

        # Map OpenRouter prefix -> LiteLLM prefix
        or_to_litellm = {
            "google": "gemini", "x-ai": "xai", "mistralai": "mistral",
            "moonshotai": "moonshot",
        }

        results = []
        for m in candidates:
            output_mods = m.get("architecture", {}).get("output_modalities") or []
            if output_mods and "text" not in output_mods:
                continue

            or_id = m.get("id", "")
            name = m.get("name", or_id)
            parts = or_id.split("/", 1)
            if len(parts) == 2:
                or_prefix, model_name = parts
                litellm_prefix = or_to_litellm.get(or_prefix, or_prefix)
                if provider_id == "anthropic":
                    model_id = model_name
                else:
                    model_id = f"{litellm_prefix}/{model_name}"
            else:
                model_id = or_id

            if query:
                q = query.lower()
                if q not in model_id.lower() and q not in name.lower():
                    continue

            results.append({
                "id": model_id,
                "name": name,
                "created": m.get("created", 0),
                "description": m.get("description", ""),
            })

        results.sort(key=lambda m: m.get("created", 0), reverse=True)
        return results[:limit]

    def _get_openrouter_models(self, query: str, limit: int) -> List[Dict]:
        """Get all OpenRouter models (for the openrouter provider)."""
        results = []
        for m in self._or_cache:
            output_mods = m.get("architecture", {}).get("output_modalities") or []
            if output_mods and "text" not in output_mods:
                continue
            or_id = m.get("id", "")
            name = m.get("name", or_id)
            model_id = f"openrouter/{or_id}"

            if query:
                q = query.lower()
                if q not in model_id.lower() and q not in name.lower():
                    continue

            results.append({
                "id": model_id,
                "name": name,
                "created": m.get("created", 0),
                "description": m.get("description", ""),
            })

        results.sort(key=lambda m: m.get("created", 0), reverse=True)
        return results[:limit]

# Singleton instance
_catalog = ModelCatalog()


def get_models_for_provider(
    provider_id: str, query: str = "", limit: int = 100
) -> List[Dict]:
    """Get models for a provider. Uses native API with OpenRouter fallback."""
    return _catalog.get_models_for_provider(provider_id, query, limit)


def get_model_description(provider_id: str, model_id: str) -> str:
    """Look up a model's description by its LiteLLM model ID."""
    models = _catalog.get_models_for_provider(provider_id, limit=500)
    for m in models:
        if m["id"] == model_id:
            return m.get("description", "")
    return ""

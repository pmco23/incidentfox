#!/usr/bin/env python3
"""Test script to verify LLM proxy works with multiple providers.

Tests three routing paths:
1. Claude: direct pass-through to Anthropic API
2. Direct providers: OpenAI, Gemini, DeepSeek, Kimi, MiniMax, Grok, Mistral
3. Via OpenRouter: Qwen, Cohere, and any model without a direct API key

Usage:
    1. Start credential-resolver:
       set -a && source .env && set +a
       .venv/bin/uvicorn credential_resolver.main:app --port 8002

    2. Run this script:
       .venv/bin/python test_models.py [filter...]
"""

import json
import sys
import time

import httpx

BASE_URL = "http://localhost:8002"

# Model definitions grouped by routing path
MODELS = {
    # === Direct to official API (pass-through) ===
    "claude (direct)": "claude-sonnet-4-20250514",

    # === Direct to official API (via LiteLLM) ===
    "openai (direct)": "openai/gpt-4o-mini",
    "gemini (direct)": "gemini/gemini-2.5-flash",
    "deepseek (direct)": "deepseek/deepseek-chat",
    "kimi (direct)": "moonshot/kimi-k2-turbo-preview",
    "minimax (direct)": "minimax/MiniMax-Text-01",
    "grok (direct)": "xai/grok-3-mini",
    "mistral (direct)": "mistral/mistral-small-latest",

    # === Cloud platforms ===
    "bedrock (aws)": "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    "deepseek (azure ai)": "azure_ai/DeepSeek-V3.2-Speciale",

    # === Via OpenRouter (models without direct API keys) ===
    "qwen (openrouter)": "openrouter/qwen/qwen-2.5-72b-instruct",
    "cohere (openrouter)": "openrouter/cohere/command-a",
}

# Anthropic Messages API format request body
REQUEST_BODY = {
    "model": "claude-sonnet-4-20250514",  # SDK default (overridden by x-llm-model header)
    "max_tokens": 1024,
    "messages": [
        {
            "role": "user",
            "content": "Say 'Hello from <your model name>!' in exactly one sentence.",
        }
    ],
}


def test_model(name: str, model_id: str) -> tuple[bool, str]:
    """Test a single model via the LLM proxy (non-streaming).

    Returns (success, message).
    """
    is_claude = model_id.startswith("claude")
    try:
        with httpx.Client(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
            }
            if is_claude:
                # Claude pass-through needs x-api-key (normally injected by ext_authz)
                import os
                headers["x-api-key"] = os.getenv("ANTHROPIC_API_KEY", "")
            else:
                headers["x-llm-model"] = model_id

            response = client.post(
                f"{BASE_URL}/v1/messages",
                headers=headers,
                json=REQUEST_BODY,
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.text[:200]}"

            data = response.json()

            # Check for Anthropic error format
            if data.get("type") == "error":
                err = data.get("error", {})
                return False, f"{err.get('type')}: {err.get('message', '')[:200]}"

            # Extract text from Anthropic response format
            content = data.get("content", [])
            text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
            text = " ".join(text_parts).strip()

            if not text:
                return False, f"Empty response. Full: {json.dumps(data)[:200]}"

            return True, text[:150]

    except httpx.TimeoutException:
        return False, "TIMEOUT (60s)"
    except Exception as e:
        return False, f"ERROR: {e}"


def test_model_streaming(name: str, model_id: str) -> tuple[bool, str]:
    """Test a single model with streaming via the LLM proxy."""
    is_claude = model_id.startswith("claude")
    body = {**REQUEST_BODY, "stream": True}
    try:
        with httpx.Client(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
            }
            if is_claude:
                import os
                headers["x-api-key"] = os.getenv("ANTHROPIC_API_KEY", "")
            else:
                headers["x-llm-model"] = model_id

            with client.stream(
                "POST",
                f"{BASE_URL}/v1/messages",
                headers=headers,
                json=body,
            ) as response:
                if response.status_code != 200:
                    error_body = response.read().decode()
                    return False, f"HTTP {response.status_code}: {error_body[:200]}"

                text_chunks = []
                event_types = set()
                for line in response.iter_lines():
                    if line.startswith("event: "):
                        event_types.add(line[7:])
                    elif line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text_chunks.append(delta.get("text", ""))
                        except json.JSONDecodeError:
                            pass

                text = "".join(text_chunks).strip()
                events = ", ".join(sorted(event_types))

                if not text:
                    return False, f"No text in stream. Events: {events}"

                return True, f"{text[:120]} [events: {events}]"

    except httpx.TimeoutException:
        return False, "TIMEOUT (60s)"
    except Exception as e:
        return False, f"ERROR: {e}"


def main():
    # Check server is running
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        print(f"Server health: {r.json()}\n")
    except Exception:
        print(f"ERROR: Server not running at {BASE_URL}")
        print("Start it with:")
        print("  set -a && source .env && set +a")
        print("  .venv/bin/uvicorn credential_resolver.main:app --port 8002")
        sys.exit(1)

    # Filter models if args provided
    models = MODELS
    if len(sys.argv) > 1:
        filter_names = [a.lower() for a in sys.argv[1:]]
        models = {k: v for k, v in MODELS.items() if any(f in k.lower() for f in filter_names)}
        if not models:
            print(f"No models match filter: {sys.argv[1:]}")
            print(f"Available: {list(MODELS.keys())}")
            sys.exit(1)

    print(f"Testing {len(models)} models (non-streaming)...\n")
    print("-" * 80)

    results = {}
    for name, model_id in models.items():
        print(f"  {name:30s} ({model_id})")
        start = time.time()
        ok, msg = test_model(name, model_id)
        elapsed = time.time() - start
        status = "PASS" if ok else "FAIL"
        results[name] = ok
        print(f"  {'':30s} [{status}] ({elapsed:.1f}s) {msg}")
        print()

    print("-" * 80)
    print(f"\nTesting {len(models)} models (streaming)...\n")
    print("-" * 80)

    stream_results = {}
    for name, model_id in models.items():
        print(f"  {name:30s} ({model_id})")
        start = time.time()
        ok, msg = test_model_streaming(name, model_id)
        elapsed = time.time() - start
        status = "PASS" if ok else "FAIL"
        stream_results[name] = ok
        print(f"  {'':30s} [{status}] ({elapsed:.1f}s) {msg}")
        print()

    print("-" * 80)
    print("\n=== SUMMARY ===\n")
    for name in models:
        sync_ok = results.get(name, False)
        stream_ok = stream_results.get(name, False)
        sync_icon = "OK" if sync_ok else "FAIL"
        stream_icon = "OK" if stream_ok else "FAIL"
        print(f"  {name:30s}  sync={sync_icon:4s}  stream={stream_icon:4s}")

    total_pass = sum(1 for v in results.values() if v) + sum(1 for v in stream_results.values() if v)
    total = len(results) + len(stream_results)
    print(f"\n  Total: {total_pass}/{total} passed")


if __name__ == "__main__":
    main()

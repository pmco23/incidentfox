#!/usr/bin/env python3
"""
Debug script to test web_search function directly
"""

import os
import sys

# Set environment
os.environ["CONFIG_BASE_URL"] = "http://incidentfox-config-service:8080"


def test_web_search():
    print("=" * 80)
    print("TESTING WEB_SEARCH FUNCTION")
    print("=" * 80)

    # 1. Set up execution context
    print("\n1. Setting up execution context...")
    from ai_agent.core.config_service import get_config_service_client
    from ai_agent.core.execution_context import (
        get_execution_context,
        set_execution_context,
    )

    client = get_config_service_client()
    team_token = (
        "bf0e51305bd84bc38331a505fcf00ca1.LwCD_zYCgm_h_zNWj35oYFq5gBSPAHAdIiGxcLU15nE"
    )

    team_config = client.fetch_effective_config(team_token=team_token)
    auth_identity = client.fetch_auth_identity(team_token=team_token)

    team_config_dict = (
        team_config.model_dump() if hasattr(team_config, "model_dump") else team_config
    )

    context = set_execution_context(
        org_id=auth_identity.org_id,
        team_node_id=auth_identity.team_node_id,
        team_config=team_config_dict,
    )

    print(f"   ✓ Context set for {auth_identity.org_id}/{auth_identity.team_node_id}")

    # 2. Test getting Tavily config from context (exactly like web_search does)
    print("\n2. Getting Tavily key (simulating web_search logic)...")

    tavily_key = None

    # Step 1: Try execution context
    ctx = get_execution_context()
    if ctx:
        print("   - Execution context found")
        config = ctx.get_integration_config("tavily")
        print(f"   - Tavily config from context: {config}")
        tavily_key = config.get("api_key") if config else None
        print(f"   - API key from config: {bool(tavily_key)}")

    # Step 2: Fallback to env var
    if not tavily_key:
        print("   - Checking env var TAVILY_API_KEY...")
        tavily_key = os.getenv("TAVILY_API_KEY")
        print(f"   - Found in env: {bool(tavily_key)}")

    # Step 3: Check if we have a key
    if not tavily_key:
        print(
            "\n   ✗ NO TAVILY KEY FOUND - web_search will return 'not configured' error"
        )
        return
    else:
        print(f"\n   ✓ Tavily key found: {tavily_key[:15]}...")

    # 3. Call Tavily API (exactly like web_search does)
    print("\n3. Calling Tavily API...")
    try:
        import httpx

        query = "latest tech news"
        max_results = 3

        print(f"   Query: {query}")
        print(f"   Max results: {max_results}")
        print("   API endpoint: https://api.tavily.com/search")

        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_key,
                "query": query,
                "max_results": min(max_results, 10),
            },
            timeout=30.0,
        )

        print(f"   Response status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"   ✗ API error: {resp.text}")
            return

        resp.raise_for_status()
        data = resp.json()

        print("   ✓ API call successful!")
        print(f"   Results count: {len(data.get('results', []))}")

        if data.get("results"):
            print("\n   First result:")
            first = data["results"][0]
            print(f"     Title: {first.get('title', '')}")
            print(f"     URL: {first.get('url', '')}")
            print(f"     Content: {first.get('content', '')[:100]}...")

    except Exception as e:
        print(f"   ✗ API call failed: {e}")
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 80)
    print("✓ SUCCESS - web_search should work!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_web_search()
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

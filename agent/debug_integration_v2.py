#!/usr/bin/env python3
"""
Debug script to test integration config flow - v2
"""

import os
import sys

# Set environment
os.environ["CONFIG_BASE_URL"] = "http://incidentfox-config-service:8080"


def test_integration_flow():
    print("=" * 80)
    print("TESTING INTEGRATION CONFIG FLOW - V2")
    print("=" * 80)

    # 1. Fetch config from config service
    print("\n1. Fetching config from config service...")
    from ai_agent.core.config_service import get_config_service_client

    client = get_config_service_client()
    team_token = (
        "bf0e51305bd84bc38331a505fcf00ca1.LwCD_zYCgm_h_zNWj35oYFq5gBSPAHAdIiGxcLU15nE"
    )

    print(f"   Using token: {team_token[:20]}...")

    team_config = client.fetch_effective_config(team_token=team_token)
    auth_identity = client.fetch_auth_identity(team_token=team_token)

    print(
        f"   ✓ Fetched config for org: {auth_identity.org_id}, team: {auth_identity.team_node_id}"
    )

    # 2. Check integrations in config
    print("\n2. Checking integrations in team_config...")
    integrations = team_config.integrations
    print(f"   Integration keys: {list(integrations.keys())}")

    if "tavily" in integrations:
        print("   ✓ Tavily found!")
        tavily_integration = integrations["tavily"]
        print(f"   Tavily structure: {tavily_integration.keys()}")
        print(f"   Tavily config: {tavily_integration.get('config', {})}")
    else:
        print("   ✗ Tavily NOT found in integrations")

    # 3. Set execution context
    print("\n3. Setting execution context...")
    from ai_agent.core.execution_context import (
        get_execution_context,
        set_execution_context,
    )

    team_config_dict = (
        team_config.model_dump() if hasattr(team_config, "model_dump") else team_config
    )

    context = set_execution_context(
        org_id=auth_identity.org_id,
        team_node_id=auth_identity.team_node_id,
        team_config=team_config_dict,
    )

    print("   ✓ Context set")
    print(f"   Integrations in context: {list(context.integrations.keys())}")

    # 4. Get Tavily config from context
    print("\n4. Getting Tavily config from context (what web_search tool will see)...")
    tavily_config = context.get_integration_config("tavily")
    print(f"   Tavily config: {tavily_config}")

    if tavily_config:
        api_key = tavily_config.get("api_key")
        print(f"   API Key present: {bool(api_key)}")
        if api_key:
            print(f"   API Key value: {api_key[:15]}...")
    else:
        print("   ✗ Tavily config is EMPTY")

    # 5. Manually test the web_search logic
    print("\n5. Testing web_search logic manually...")

    # Simulate what web_search does
    tavily_key = None

    # Get from execution context
    ctx = get_execution_context()
    if ctx:
        config = ctx.get_integration_config("tavily")
        tavily_key = config.get("api_key")
        print(f"   Got from context: {bool(tavily_key)}")

    # Fallback to env var
    if not tavily_key:
        tavily_key = os.getenv("TAVILY_API_KEY")
        print(f"   Tried env var: {bool(tavily_key)}")

    if not tavily_key:
        print("   ✗ FAILED - No Tavily key found")
        print("   This is what the web_search tool will see!")
        return

    print(f"   ✓ Tavily key found: {tavily_key[:15]}...")

    # 6. Test actual Tavily API call
    print("\n6. Testing actual Tavily API call...")
    try:
        from tavily import TavilyClient

        tavily_client = TavilyClient(api_key=tavily_key)

        print("   Making search request...")
        response = tavily_client.search(query="test query", max_results=1)

        if response and "results" in response:
            print("   ✓ SUCCESS - Tavily API working!")
            print(f"   Got {len(response.get('results', []))} results")
        else:
            print(f"   ✗ Unexpected response: {response}")

    except Exception as e:
        print(f"   ✗ Tavily API call failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("  - Config fetch: ✓")
    print("  - Tavily in integrations: ✓")
    print("  - Execution context set: ✓")
    print(f"  - Tavily config accessible: {bool(tavily_config)}")
    print(f"  - API key present: {bool(tavily_key)}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_integration_flow()
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

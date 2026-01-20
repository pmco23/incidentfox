#!/usr/bin/env python3
"""
Debug script to test integration config flow.
"""

import os
import sys

# Set environment
os.environ["CONFIG_BASE_URL"] = "http://incidentfox-config-service:8080"


def test_integration_flow():
    print("=" * 80)
    print("TESTING INTEGRATION CONFIG FLOW")
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
    from ai_agent.core.execution_context import set_execution_context

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
    print("\n4. Getting Tavily config from context...")
    tavily_config = context.get_integration_config("tavily")
    print(f"   Tavily config: {tavily_config}")

    if tavily_config:
        api_key = tavily_config.get("api_key")
        print(f"   API Key: {api_key[:20] if api_key else 'NOT FOUND'}...")
    else:
        print("   ✗ Tavily config is EMPTY")

    # 5. Test web_search tool
    print("\n5. Testing web_search tool...")
    from ai_agent.tools.agent_tools import web_search

    result = web_search("test query")
    print(f"   Result: {result[:200]}...")

    if "Web search not configured" in result:
        print("   ✗ FAILED - Still getting 'not configured' error")
    else:
        print("   ✓ SUCCESS - Web search is working!")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        test_integration_flow()
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

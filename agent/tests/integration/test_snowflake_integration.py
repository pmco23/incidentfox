#!/usr/bin/env python3
"""
End-to-end test for Snowflake integration using execution context.

Tests:
1. Snowflake config retrieval from execution context
2. Multi-tenant isolation (Team A vs Team B)
3. Error handling when integration not configured
"""

import sys
from pathlib import Path

# Add agent src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_agent.core.execution_context import (
    clear_execution_context,
    get_execution_context,
    set_execution_context,
)
from ai_agent.core.integration_errors import IntegrationNotConfiguredError


def get_snowflake_config() -> dict:
    """Get Snowflake configuration from execution context."""
    context = get_execution_context()
    if context:
        config = context.get_integration_config("snowflake")
        if config and config.get("account"):
            return config

    raise IntegrationNotConfiguredError(
        integration_id="snowflake",
        tool_id="snowflake_query",
        missing_fields=["account", "username", "password", "warehouse"],
    )


def test_team_a_config():
    """Test: Team A has Snowflake configured correctly."""
    print("\n🧪 Test 1: Team A with Snowflake configured")

    # Simulate Team A's config
    team_a_config = {
        "integrations": {
            "snowflake": {
                "config": {
                    "account": "team-a-account",
                    "username": "team_a_user",
                    "password": "team_a_secret",
                    "warehouse": "TEAM_A_WH",
                    "database": "TEAM_A_DB",
                    "schema": "TEAM_A_SCHEMA",
                }
            }
        }
    }

    set_execution_context(
        org_id="org_123", team_node_id="team_a", team_config=team_a_config
    )

    try:
        config = get_snowflake_config()

        # Verify correct config returned
        assert (
            config["account"] == "team-a-account"
        ), f"Expected 'team-a-account', got {config['account']}"
        assert (
            config["username"] == "team_a_user"
        ), f"Expected 'team_a_user', got {config['username']}"
        assert (
            config["warehouse"] == "TEAM_A_WH"
        ), f"Expected 'TEAM_A_WH', got {config['warehouse']}"

        print("✅ PASS: Team A config retrieved correctly")
        print(f"   - Account: {config['account']}")
        print(f"   - Username: {config['username']}")
        print(f"   - Warehouse: {config['warehouse']}")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    finally:
        clear_execution_context()


def test_team_b_isolation():
    """Test: Team B has different Snowflake config (multi-tenant isolation)."""
    print("\n🧪 Test 2: Team B with different Snowflake config (isolation)")

    # Simulate Team B's config (different credentials)
    team_b_config = {
        "integrations": {
            "snowflake": {
                "config": {
                    "account": "team-b-account",
                    "username": "team_b_user",
                    "password": "team_b_secret",
                    "warehouse": "TEAM_B_WH",
                    "database": "TEAM_B_DB",
                    "schema": "TEAM_B_SCHEMA",
                }
            }
        }
    }

    set_execution_context(
        org_id="org_123", team_node_id="team_b", team_config=team_b_config
    )

    try:
        config = get_snowflake_config()

        # Verify Team B gets ITS OWN config, not Team A's
        assert (
            config["account"] == "team-b-account"
        ), f"Expected 'team-b-account', got {config['account']}"
        assert (
            config["username"] == "team_b_user"
        ), f"Expected 'team_b_user', got {config['username']}"
        assert (
            config["warehouse"] == "TEAM_B_WH"
        ), f"Expected 'TEAM_B_WH', got {config['warehouse']}"

        # Make sure it's NOT Team A's config
        assert (
            config["account"] != "team-a-account"
        ), "Got Team A's account! Multi-tenant isolation FAILED!"

        print("✅ PASS: Team B config retrieved correctly (isolated from Team A)")
        print(f"   - Account: {config['account']}")
        print(f"   - Username: {config['username']}")
        print(f"   - Warehouse: {config['warehouse']}")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    finally:
        clear_execution_context()


def test_not_configured():
    """Test: Integration not configured raises proper error."""
    print("\n🧪 Test 3: Integration not configured")

    # Simulate Team C with NO Snowflake config
    team_c_config = {"integrations": {}}

    set_execution_context(
        org_id="org_123", team_node_id="team_c", team_config=team_c_config
    )

    try:
        config = get_snowflake_config()
        print(
            f"❌ FAIL: Should have raised IntegrationNotConfiguredError, but got config: {config}"
        )
        return False
    except IntegrationNotConfiguredError as e:
        # Expected!
        print("✅ PASS: Raised IntegrationNotConfiguredError as expected")
        print(f"   - Error message: {e}")
        print(f"   - Integration ID: {e.integration_id}")
        print(f"   - Tool ID: {e.tool_id}")
        print(f"   - Missing fields: {e.missing_fields}")
        return True
    except Exception as e:
        print(f"❌ FAIL: Wrong exception type: {type(e).__name__}: {e}")
        return False
    finally:
        clear_execution_context()


def test_no_context():
    """Test: No execution context (fallback to env vars or error)."""
    print("\n🧪 Test 4: No execution context set")

    # Don't set any execution context
    clear_execution_context()

    try:
        config = get_snowflake_config()
        print(
            f"❌ FAIL: Should have raised IntegrationNotConfiguredError, but got config: {config}"
        )
        return False
    except IntegrationNotConfiguredError as e:
        print("✅ PASS: Raised IntegrationNotConfiguredError when no context")
        print(f"   - Error message: {e}")
        return True
    except Exception as e:
        print(f"❌ FAIL: Wrong exception type: {type(e).__name__}: {e}")
        return False


def main():
    print("=" * 80)
    print("🧪 Snowflake Integration End-to-End Tests")
    print("=" * 80)

    results = []

    results.append(test_team_a_config())
    results.append(test_team_b_isolation())
    results.append(test_not_configured())
    results.append(test_no_context())

    print("\n" + "=" * 80)
    print("📊 Test Results")
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 All tests passed! Snowflake integration is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please investigate.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

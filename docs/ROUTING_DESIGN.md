# Webhook Routing Design

## Overview

This document describes how IncidentFox routes incoming webhooks to the correct team and loads team-specific configuration.

## Problem Statement

When a webhook arrives (from Incident.io, Slack, GitHub, etc.), we need to:
1. **Identify which team** should handle this event
2. **Load that team's configuration** (agent prompts, integrations, credentials)
3. **Track the agent run** against the correct org/team

Currently, we use a hardcoded `INCIDENTFOX_TEAM_TOKEN` environment variable, which only works for single-team deployments.

## Solution: Multi-Source Routing

Each team configures **routing identifiers** - unique values that identify events belonging to that team.

### Routing Schema

```yaml
team: platform-sre
  routing:
    # Slack channels this team owns
    slack_channel_ids:
      - "C0A4967KRBM"
      - "C0B5678XYZ"
    
    # Incident.io team IDs (from their Catalog)
    incidentio_team_ids:
      - "01KCSZ7FHG3D9XZH0NQBG2BDD2"
    
    # Incident.io alert source IDs (if dedicated per team)
    incidentio_alert_source_ids:
      - "01KEGMSPPCKFPYHT2ZSNQ7WY3J"
    
    # PagerDuty service IDs
    pagerduty_service_ids:
      - "PXXXXXX"
    
    # Coralogix team names (normalized to lowercase)
    coralogix_team_names:
      - "platform-sre"
      - "platform"
    
    # GitHub repositories (owner/repo format)
    github_repos:
      - "incidentfox/mono-repo"
      - "incidentfox/api"
    
    # Services this team owns (for service-based routing)
    services:
      - "payment"
      - "checkout"
      - "cart"
```

### Validation Rules

1. **Uniqueness**: Each identifier can only belong to ONE team within an org
   - If team A claims `slack_channel_ids: ["C123"]`, team B cannot claim the same
   - Validation happens at config save time

2. **Normalization**: Values are normalized before comparison
   - Lowercase
   - Trim whitespace
   - For team names: remove special characters, replace spaces with hyphens

3. **Optional fields**: Teams only configure what they use

## Lookup API

### Endpoint

```
POST /api/v1/internal/routing/lookup
```

### Request

```json
{
  "org_id": "extend",  // Optional - if known
  "identifiers": {
    "slack_channel_id": "C0A4967KRBM",
    "incidentio_team_id": "01KCSZ7FHG3D9XZH0NQBG2BDD2",
    "coralogix_team_name": "platform-sre",
    "github_repo": "incidentfox/mono-repo",
    "service": "payment"
  }
}
```

Caller provides ALL identifiers they have from the webhook. The lookup tries them in priority order.

### Response

```json
{
  "found": true,
  "org_id": "extend",
  "team_node_id": "extend-sre",
  "matched_by": "slack_channel_id",
  "matched_value": "C0A4967KRBM",
  "team_token": "55a3eb516f3043a498e76a75232996e7.xxx"  // For fetching full config
}
```

Or if not found:

```json
{
  "found": false,
  "tried": ["slack_channel_id", "incidentio_team_id", "service"],
  "suggestion": "Configure routing for one of: C0A4967KRBM, payment"
}
```

### Lookup Priority Order

1. `incidentio_team_id` - Most specific, from Incident.io's own routing
2. `pagerduty_service_id` - Specific to PagerDuty
3. `slack_channel_id` - Reliable, channels are team-owned
4. `github_repo` - For CI/CD events
5. `coralogix_team_name` - From observability platform
6. `incidentio_alert_source_id` - Less specific (often org-wide)
7. `service` - Fallback based on service ownership

## Webhook Handler Changes

### Current Flow (Single-Team)

```python
# api_server.py
effective_token = team_token or os.getenv("INCIDENTFOX_TEAM_TOKEN")
team_config = client.fetch_effective_config(team_token=effective_token)
```

### New Flow (Multi-Team)

```python
# api_server.py
async def _run_investigation_for_incident(...):
    # Extract identifiers from payload
    identifiers = {
        "slack_channel_id": extra_context.get("slack_channel_id"),
        "incidentio_team_id": _extract_incidentio_team(raw_payload),
        "incidentio_alert_source_id": raw_payload.get("alert_source_id"),
        "service": service,
    }
    
    # Lookup team via routing
    routing_result = await _lookup_team_routing(identifiers)
    
    if routing_result.found:
        team_token = routing_result.team_token
        team_config = client.fetch_effective_config(team_token=team_token)
        auth_identity = AuthIdentity(
            org_id=routing_result.org_id,
            team_node_id=routing_result.team_node_id,
            ...
        )
    else:
        # Fallback to env var for backwards compatibility
        team_token = os.getenv("INCIDENTFOX_TEAM_TOKEN")
        ...
```

## Database Schema

### Option A: Store in team config (JSON)

Already supported - routing is part of `TeamLevelConfig`:

```json
{
  "routing": {
    "slack_channel_ids": ["C0A4967KRBM"],
    "services": ["payment", "checkout"]
  }
}
```

### Option B: Dedicated routing table (for fast lookups)

```sql
CREATE TABLE routing_identifiers (
    id UUID PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(64) NOT NULL,
    identifier_type VARCHAR(32) NOT NULL,  -- 'slack_channel_id', 'github_repo', etc.
    identifier_value VARCHAR(256) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(org_id, identifier_type, identifier_value),  -- Enforce uniqueness
    INDEX(identifier_type, identifier_value)  -- Fast lookups
);
```

**Recommendation**: Start with Option A (JSON in config), migrate to Option B if performance becomes an issue.

## Identifier Extraction

### From Incident.io Webhook

```python
def _extract_incidentio_identifiers(payload: dict) -> dict:
    identifiers = {}
    
    # Alert source ID
    alert_data = payload.get(payload.get("event_type"), {})
    identifiers["incidentio_alert_source_id"] = alert_data.get("alert_source_id")
    
    # Team from attributes
    for attr in alert_data.get("attributes", []):
        if attr.get("attribute", {}).get("name") == "Team":
            value = attr.get("value", {})
            identifiers["incidentio_team_id"] = value.get("literal") or value.get("id")
    
    # Service from title (heuristic)
    title = alert_data.get("title", "").lower()
    for svc in ["payment", "checkout", "cart", ...]:
        if svc in title:
            identifiers["service"] = svc
            break
    
    return identifiers
```

### From Coralogix (via Incident.io)

Coralogix sends `team_name` in its webhook to Incident.io. This gets passed through:

```python
def _extract_coralogix_identifiers(payload: dict) -> dict:
    metadata = payload.get("metadata", {})
    return {
        "coralogix_team_name": metadata.get("team_name", "").lower().strip(),
        "service": metadata.get("subsystem_name", "").lower().strip(),
    }
```

### From GitHub Webhook

```python
def _extract_github_identifiers(payload: dict) -> dict:
    repo = payload.get("repository", {})
    return {
        "github_repo": repo.get("full_name"),  # "owner/repo"
    }
```

### From Slack Event

```python
def _extract_slack_identifiers(payload: dict) -> dict:
    event = payload.get("event", {})
    return {
        "slack_channel_id": event.get("channel"),
    }
```

## Migration Path

### Phase 1: Backwards Compatible (Current)
- Keep `INCIDENTFOX_TEAM_TOKEN` working
- Add routing config support
- Routing lookup is optional enhancement

### Phase 2: Routing-First
- Webhook handlers try routing lookup first
- Fall back to env var if not found
- Log warnings for unconfigured routes

### Phase 3: Full Multi-Tenant
- Remove env var fallback for SaaS
- Require routing config for all teams
- Admin UI for managing routing

## Testing

### Unit Tests

```python
def test_routing_lookup_by_slack_channel():
    # Team A owns channel C123
    config_a = {"routing": {"slack_channel_ids": ["C123"]}}
    
    result = lookup_routing({"slack_channel_id": "C123"})
    assert result.found == True
    assert result.team_node_id == "team-a"

def test_routing_validation_rejects_duplicates():
    # Team A already has channel C123
    # Team B tries to claim same channel
    with pytest.raises(ValidationError):
        save_team_config("team-b", {"routing": {"slack_channel_ids": ["C123"]}})
```

### Integration Tests

```python
async def test_incidentio_webhook_routes_to_correct_team():
    # Configure team routing
    await setup_team_routing("extend-sre", {
        "slack_channel_ids": ["C0A4967KRBM"],
        "services": ["payment"]
    })
    
    # Send webhook
    response = await client.post("/webhooks/incidentio", json={
        "event_type": "public_alert.alert_created_v1",
        "public_alert.alert_created_v1": {
            "title": "Payment Service - Error Rate",
            ...
        }
    })
    
    # Verify routed to correct team
    assert response.status == 200
    agent_run = await get_last_agent_run()
    assert agent_run.team_node_id == "extend-sre"
```

## Open Questions

1. **Cross-org routing?** Can same Slack channel belong to different teams in different orgs?
   - Recommendation: Yes, scope uniqueness to org level

2. **Wildcard matching?** Should `github_repos: ["incidentfox/*"]` match all repos?
   - Recommendation: No wildcards in v1, explicit list only

3. **Auto-discovery?** Should we auto-populate from Incident.io/Slack APIs?
   - Recommendation: Nice-to-have for v2, manual config for v1

4. **Audit trail?** Log when routing config changes?
   - Recommendation: Yes, use existing config audit system


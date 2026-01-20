# Using the IncidentFox Config Service (for other services)

This document describes how other services (agents, automation jobs, internal tools) should call the IncidentFox Config Service and parse team configuration.

## Concepts

- **Config is stored per org-node** (`org_nodes`) in PostgreSQL as **JSONB** (`node_configs.config_json`).
- A team’s **effective config** is computed by **walking the org tree lineage** (root → … → team) and **deep-merging** configs.
- A caller typically authenticates as a **team** using an opaque bearer token that maps to exactly one `(org_id, team_node_id)`.

## Which endpoints should a service use?

### Get the team’s effective config (recommended)

- **`GET /api/v1/config/me/effective`**
- Returns the final merged config for the authenticated team.
- This is what an agent should use at runtime.

### Identify the caller (recommended for UI + debugging)

- **`GET /api/v1/auth/me`**
- Accepts the same auth headers as other endpoints.
- Returns a lightweight identity object so UIs can:
  - show/hide admin pages
  - route users cleanly
  - avoid confusing 403s by disabling admin actions for team users

Example response:

```json
{
  "role": "team",
  "auth_kind": "team_token",
  "org_id": "org1",
  "team_node_id": "teamA",
  "subject": null,
  "email": null,
  "can_write": true,
  "permissions": ["team:read", "team:write"]
}
```

### Get raw lineage + per-node configs (debug / explainability)

- **`GET /api/v1/config/me/raw`**
- Returns:
  - `lineage`: ordered list of nodes from root → team
  - `configs`: a map of `node_id -> config_json`
- Useful for “why is this value set?” debugging and UI explainability.

### Get team config history (UI history / diff)

- **`GET /api/v1/config/me/audit`**
- Returns the authenticated team’s config change history (newest-first), including:
  - `version`
  - `changed_at`, `changed_by`
  - `diff` (best-effort minimal diff)
  - `full_config` (snapshot for that version; can be omitted via `include_full=false`)

Query params:
- `limit` (default 50)
- `include_full` (default true)

### Update team overrides (team-owned edits)

- **`PUT /api/v1/config/me`**
- **PATCH semantics**: payload is deep-merged into existing team overrides.
- Immutable fields (e.g. `team_name`) are rejected.

## Authentication (team token)

Send the team token as:

- `Authorization: Bearer <TEAM_TOKEN>`

The service resolves `<TEAM_TOKEN>` to a single team identity:

- `(org_id, team_node_id)`

and `/me/*` endpoints operate on that team.

## Mock response (effective config)

Example response from `GET /api/v1/config/me/effective`:

```json
{
  "tokens_vault_path": {
    "openai_token": "vault://incidentfox/prod/openai",
    "slack_bot": "vault://incidentfox/prod/slack-bot"
  },
  "slack_group_to_ping": "@oncall-platform",
  "slack_channel": "#incidents-platform",
  "google_account": "incidentfox-oncall@incidentfox.com",
  "confluence_space": "SRE",
  "mcp_servers": ["grafana", "pagerduty", "aws"],
  "feature_flags": {
    "enable_auto_mitigation": true,
    "enable_write_actions": false
  },
  "knowledge_source": {
    "grafana": ["prod-k8s", "prod-logs"],
    "google": ["drive:folder/oncall-runbooks"],
    "confluence": ["space:SRE"]
  },
  "agents": {
    "investigation_agent": {
      "prompt": "You are the IncidentFox oncall investigation agent...",
      "disable_default_tools": ["shell"],
      "enable_extra_tools": ["github", "datadog"]
    },
    "code_fix_agent": {
      "enabled": false,
      "prompt": ""
    }
  },
  "alerts": {
    "disabled": ["cpu_throttle_high", "disk_pressure"]
  }
}
```

Notes:
- The service validates known fields using `TeamLevelConfig`, but it also allows additional keys (for forward-compat) because the model is configured with `extra="allow"`.

## Python example: fetch + parse config

This example shows:
- fetching `/me/effective`
- parsing into the Pydantic model (`TeamLevelConfig`) for structured access
- reading extra/unmodeled fields safely

```python
import os
import httpx

from src.core.config_models import TeamLevelConfig

CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL", "http://localhost:8080")
TEAM_TOKEN = os.environ["INCIDENTFOX_TEAM_TOKEN"]  # e.g. "tokid.toksecret"


def fetch_team_config_effective() -> TeamLevelConfig:
    url = f"{CONFIG_BASE_URL}/api/v1/config/me/effective"
    headers = {"Authorization": f"Bearer {TEAM_TOKEN}"}

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # Typed validation (Pydantic v2)
    return TeamLevelConfig.model_validate(data)


cfg = fetch_team_config_effective()

# Typed fields
print("MCP servers:", cfg.mcp_servers)
print("Slack group:", cfg.slack_group_to_ping)
print("Grafana sources:", (cfg.knowledge_source.grafana if cfg.knowledge_source else []))

# Extra/unmodeled fields (because extra='allow')
all_fields = cfg.model_dump()
print("Slack channel:", all_fields.get("slack_channel"))
print("Feature flags:", all_fields.get("feature_flags", {}))
```

## Evolving the config schema (best practice)

Because configs are stored as JSONB, adding fields is typically **backward-compatible** and **does not require DB migrations**.

Recommended approach:

1. **Decide the canonical JSON shape** (keys + nesting).
2. Add new fields to the typed model in `src/core/config_models.py` (so teams/agents get validation + autocomplete).
3. Keep `extra="allow"` so older configs and future keys don’t break runtime parsing.
4. Update this doc and `README.md` to reflect new fields.



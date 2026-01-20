# IncidentFox Config Service - Technical Specification (Updated)

## Overview

The IncidentFox Config Service is a hierarchical configuration management system designed to work as part of the IncidentFox incident management platform. It provides inheritance, validation, and a UI for SRE teams to manage effective team configuration. Alert-name matching is NOT required at this stage; configuration resolution is purely hierarchical (org → group → team) with team-level overrides.

## Architecture Context

### System Integration (Simplified: Direct RDS)

The Config Service operates as a standalone enterprise service that:
- Authenticates teams (opaque bearer tokens) and enforces team-scoped authorization
- Reads/writes configuration data directly in **PostgreSQL (AWS RDS)** via a DB client layer in this repo

### Data Flow

```
IncidentFox Agent / Config UI → Config Service → AWS RDS PostgreSQL
       (opaque team token)       (direct SQL via DB client)

Flow:
1) Team authenticates to Config UI/Service with an opaque bearer token issued by admin (managed by Config Service)
2) Config Service fetches the team's lineage in the org graph and the base configs for each ancestor via Postgres
3) Config Service computes effective team config by inheritance across the lineage (root → ... → leaf/team)
4) Team updates only their team overrides; Config Service persists to Postgres
```

## Core Requirements

### 1. Hierarchical Configuration Management

**Purpose**: Enable organizations to set default configurations at the organization and group levels, with team-specific overrides. No alert-name matching is required.

**Key Features**:
- **Organization Level**: Default settings for all teams
- **Intermediate Groups/Units**: Any number of hierarchy levels set by admin (org graph)
- **Team Level**: Overrides for specific teams (no regex matching)
- **Configuration Inheritance**: Effective config = deep-merge along lineage (root → ... → team), later levels override earlier ones

### 2. Configuration Resolution Engine

**Purpose**: Resolve the effective team configuration using strict hierarchical merging without pattern matching.

**Resolution Order**:
Given lineage L = [root_org, group_a, group_b, ..., team_x], compute:
effective = deep_merge(root_org, group_a, group_b, ..., team_x)

**Algorithm**:
- Fetch lineage for the team (ordered list of ancestor nodes in the org graph) from Postgres
- Fetch config blob for each node in lineage (nodes may omit fields; partials allowed)
- Deep-merge dictionaries in order: earliest ancestor to leaf/team (later wins)
- Enforce immutables (e.g., `team_name` cannot be overridden) at the final step
- Guardrails: detect cycles, max depth (configurable), payload size limits

### 3. Persistence & Database Integration

**Purpose**: Persist and retrieve configurations directly in **PostgreSQL (AWS RDS)**. The Config Service owns the schema and data access layer.

**Storage Strategy**:
- **Node-scoped**: Configuration objects stored per node in the org graph (org / intermediate units / team)
- **JSON format**: Store canonical JSONB; YAML support optional for export/import
- **Caching**: In-memory caching for performance with cache invalidation
- **Versioning/Audit**: Track configuration changes over time in DB (append-only audit table)

**Database Schema Requirements (owned by Config Service)**:
- `org_nodes` (org_id, node_id, parent_id, node_type, name, created_at, updated_at)\n+  - Constraints: `(org_id, node_id)` PK, parent FK within org\n+  - Indexes: `(org_id, parent_id)`, `(org_id, node_type)`\n+- `node_configs` (org_id, node_id, config_json jsonb, version int, updated_at, updated_by)\n+  - Constraints: `(org_id, node_id)` PK, FK to `org_nodes`\n+  - Indexes: `(org_id, updated_at)`\n+- `team_tokens` (org_id, team_node_id, token_id, token_hash, issued_at, revoked_at, issued_by)\n+  - Supports team-scoped JWT or opaque tokens\n+- `node_config_audit` (org_id, node_id, version, changed_at, changed_by, diff_json jsonb, full_config_json jsonb)\n+  - Append-only audit log

### 4. Service Layer Architecture

**Purpose**: Provide clean service interfaces for configuration management and a UI experience for teams to view and edit their effective config.

**Core Services**:

#### ConfigService (this repo)
- `get_node_config(org_id, node_id)` - Fetch single node config via DB client + cache
- `get_lineage(org_id, team_id)` - Fetch lineage nodes via DB client + cache
- `get_team_overrides(org_id, team_id)` - Fetch team node config
- `save_team_overrides(org_id, team_id, overrides)` - Persist and invalidate caches + write audit record
- `get_effective_team_config(org_id, team_id)` - Fetch lineage, batch-load node configs, N-level deep-merge
- `validate_config_blob(config_obj)` - Validate override payload against schema
- `clear_cache(keys)` - Clear configuration cache

#### IncidentService
Out of scope for this iteration (no alert-name matching or incident coupling required). Can be reintroduced later.

### 5. Configuration Schema (New Fields)

**Purpose**: Define the structure and validation rules for hierarchical configurations focusing on team-level overrides and the new fields.

**Schema Components (Org/Group/Team config objects share the same shape; team overrides may be partial; depth is unbounded)**:

```python
class TokensVaultPaths(BaseModel):
    openai_token: Optional[str] = None
    slack_bot: Optional[str] = None
    glean: Optional[str] = None
    # etc. (extensible)

class AgentToggles(BaseModel):
    prompt: str = ""
    enabled: Optional[bool] = None  # if omitted, inherit
    disable_default_tools: List[str] = []
    enable_extra_tools: List[str] = []

class AgentsConfig(BaseModel):
    investigation_agent: AgentToggles
    code_fix_agent: AgentToggles
    # more agents can be added as optional fields

class KnowledgeSources(BaseModel):
    grafana: List[str] = []
    google: List[str] = []
    confluence: List[str] = []
    # etc.

class AlertsConfig(BaseModel):
    disabled: List[str] = []

class TeamLevelConfig(BaseModel):
    team_name: str  # immutable at team level (display only in UI)
    tokens_vault_path: TokensVaultPaths
    mcp_servers: List[str] = []
    a2a_agents: List[str] = []
    slack_group_to_ping: Optional[str] = None
    knowledge_source: KnowledgeSources
    agents: AgentsConfig
    alerts: AlertsConfig

    class Config:
        extra = "allow"  # forward compatible for new keys
```

Notes:
- Org and intermediate nodes use the same shape but do not include `team_name`.
- Team overrides may be partial; deep-merge applies across N levels to compute the effective config.

### 6. Backend API (Config Service) & CLI

**Purpose**: Provide REST endpoints used by the UI and optional CLI helpers for debugging.

**Service Endpoints (Config Service):**
- `GET /api/v1/config/me/effective` → returns effective config for the authenticated team (N-level merge)
- `GET /api/v1/config/me/raw` → returns lineage node list and each node's raw config
- `PUT /api/v1/config/me` → updates team overrides (server validates immutable fields)
- `GET /health` → health probe

Auth:
- Team provides an opaque bearer token issued by admin (managed by Config Service). Config Service resolves token → {org_id, team_node_id} via DB.
- Admin auth supports `ADMIN_TOKEN` and optional OIDC (human SSO).

Optional CLI (local dev):
- `config-cli me` (show effective)
- `config-cli edit --file overrides.json` (apply team overrides)

**Output Format**: JSON responses with effective config and validation errors when applicable.

### 7. Performance Requirements

**Caching Strategy**:
- Cache effective/raw config per team with TTL (in-memory or Redis)
- Safe invalidation: bump a per-org **epoch** on any write (team override, node config, org graph change)

**Optimization**:
- Deep-merge implemented iteratively across arbitrary-length lists
- Batch-load configs for all nodes in lineage in one DB query
- Keep cache keys low-cardinality; avoid per-request unbounded key creation

### 8. Security & Validation

**Validation**:
- Configuration schema validation using Pydantic (new fields)
- Immutable fields enforced on server (`team_name` cannot be changed)
- Input sanitization
- Hierarchical deep-merge validation (e.g., types must align across levels)

**Access Control**:
- Opaque bearer tokens for teams (stored hashed, revocable)
- Admin auth supports `ADMIN_TOKEN` and optional OIDC (human SSO)
- Only allow updates to the authenticated team’s overrides
- Audit logging for changes (stored in `node_config_audit`)
- Rate limiting and basic DoS protections
- Guard against lineage spoofing by always deriving lineage from the DB for the authenticated team

### 9. Configuration Example (JSON)

Effective config returned by `GET /api/v1/config/me/effective` for a team might look like:

```json
{
  "team_name": "platform-devops",
  "tokens_vault_path": {
    "openai_token": "vault://org/acme/teams/platform-devops/openai",
    "slack_bot": "vault://org/acme/teams/platform-devops/slack-bot",
    "glean": null
  },
  "mcp_servers": ["mcps://grafana", "mcps://k8s"],
  "a2a_agents": ["investigation", "code_fix"],
  "slack_group_to_ping": "@platform-oncall",
  "knowledge_source": {
    "grafana": ["dash/123", "dash/456"],
    "google": ["drive:folder/abc"],
    "confluence": ["space:PLAT:runbooks"]
  },
  "agents": {
    "investigation_agent": {
      "prompt": "Investigate incident context and propose next actions",
      "disable_default_tools": [],
      "enable_extra_tools": ["grafana", "k8s"]
    },
    "code_fix_agent": {
      "enabled": true,
      "prompt": "Provide minimal, safe hotfix suggestions",
      "disable_default_tools": ["db-write"],
      "enable_extra_tools": ["repo-read"]
    }
  },
  "alerts": {
    "disabled": ["low-noise", "chatter"]
  }
}
```

## Scope (V0)

This document describes the **current** system (direct RDS persistence, org-tree inheritance, UI/Admin API) and intentionally avoids historical plans and deprecated integrations.


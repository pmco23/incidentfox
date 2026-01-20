# Config Service - Database Schema

PostgreSQL RDS database schema.

---

## Tables

### `org_nodes`

Organization hierarchy (org → team).

| Column | Type | Description |
|--------|------|-------------|
| `org_id` | VARCHAR | Organization ID (PK part) |
| `node_id` | VARCHAR | Node ID (PK part) |
| `parent_node_id` | VARCHAR | Parent node (NULL for root org) |
| `node_type` | VARCHAR | 'org' or 'team' |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

**Primary Key**: `(org_id, node_id)`

**Example**:
```
org_id='extend', node_id='extend', node_type='org', parent=NULL
org_id='extend', node_id='platform-team', node_type='team', parent='extend'
org_id='extend', node_id='platform-sre', node_type='team', parent='extend'
```

---

### `node_configurations`

JSON configuration per node.

| Column | Type | Description |
|--------|------|-------------|
| `org_id` | VARCHAR | Organization ID (PK part) |
| `node_id` | VARCHAR | Node ID (PK part) |
| `config_json` | JSONB | Configuration (agents, tools, routing, etc.) |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

**Primary Key**: `(org_id, node_id)`

**JSONB Structure**:
```json
{
  "agents": {...},
  "tools": {"enabled": [...], "disabled": [...]},
  "routing": {"slack_channel_ids": [...], "services": [...]},
  "integrations": {"coralogix": {"api_key": "...", "domain": "..."}, ...},
  "notifications": {"default_slack_channel_id": "C123"}
}
```

---

### `team_tokens`

Team-scoped authentication tokens.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Token ID (PK) |
| `org_id` | VARCHAR | Organization ID |
| `team_node_id` | VARCHAR | Team node ID |
| `token` | VARCHAR | Opaque token string |
| `description` | VARCHAR | Token purpose |
| `created_at` | TIMESTAMP | Creation time |
| `expires_at` | TIMESTAMP | Expiration (NULL = never) |

**Primary Key**: `id`

**Token Format**: `{org_id}.{team_node_id}.{random_suffix}`

Example: `extend.extend-sre.J2KnE8rVmCfPWq`

---

### `org_admin_tokens`

Org-scoped admin tokens.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Token ID (PK) |
| `org_id` | VARCHAR | Organization ID |
| `token` | VARCHAR | Opaque token string |
| `description` | VARCHAR | Token purpose |
| `created_at` | TIMESTAMP | Creation time |
| `expires_at` | TIMESTAMP | Expiration (NULL = never) |

**Primary Key**: `id`

**Token Format**: `{org_id}.{random_suffix}`

Example: `extend.xEyGnPw3RCH1l08q2gSb8A`

---

### `agent_runs`

Agent execution history.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Run ID (PK) |
| `org_id` | VARCHAR | Organization ID |
| `team_node_id` | VARCHAR | Team node ID |
| `agent_name` | VARCHAR | Agent that executed |
| `status` | VARCHAR | 'success', 'error', 'timeout' |
| `input_message` | TEXT | User's input |
| `output` | TEXT | Agent's output |
| `duration_seconds` | FLOAT | Execution time |
| `created_at` | TIMESTAMP | Start time |
| `completed_at` | TIMESTAMP | End time |

**Primary Key**: `id`

---

### `integration_schemas`

Integration metadata and field schemas.

| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR | Integration ID (PK) - e.g. 'coralogix' |
| `name` | VARCHAR | Display name - e.g. 'Coralogix' |
| `description` | TEXT | Integration description |
| `category` | VARCHAR | 'observability', 'incident_management', etc. |
| `logo_url` | VARCHAR | Logo image URL |
| `fields` | JSONB | Array of field definitions |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

**Primary Key**: `id`

**Fields JSONB Structure**:
```json
[
  {
    "name": "api_key",
    "type": "string",
    "required": true,
    "display_name": "API Key",
    "description": "Coralogix Personal API Key",
    "secret": true
  },
  {
    "name": "domain",
    "type": "string",
    "required": true,
    "display_name": "Domain",
    "description": "Coralogix domain (e.g. cx498.coralogix.com)"
  }
]
```

---

## Indexes

```sql
-- org_nodes indexes
CREATE INDEX idx_org_nodes_parent ON org_nodes(org_id, parent_node_id);
CREATE INDEX idx_org_nodes_type ON org_nodes(org_id, node_type);

-- node_configurations indexes
CREATE INDEX idx_node_config_org ON node_configurations(org_id);

-- agent_runs indexes
CREATE INDEX idx_agent_runs_org_team ON agent_runs(org_id, team_node_id);
CREATE INDEX idx_agent_runs_created ON agent_runs(created_at DESC);

-- team_tokens indexes
CREATE INDEX idx_team_tokens_token ON team_tokens(token);
CREATE INDEX idx_team_tokens_org_team ON team_tokens(org_id, team_node_id);

-- org_admin_tokens indexes
CREATE INDEX idx_org_admin_tokens_token ON org_admin_tokens(token);
CREATE INDEX idx_org_admin_tokens_org ON org_admin_tokens(org_id);
```

---

## Migrations

Alembic migrations in `config_service/alembic/versions/`.

### Run Migrations

```bash
cd config_service
alembic upgrade head
```

### Create Migration

```bash
alembic revision -m "description"
```

---

## Important Notes

### JSONB Modification

SQLAlchemy doesn't detect in-place modifications to JSONB columns:

```python
# ❌ Won't work
config_row.config_json['tools']['enabled'].append('new_tool')
session.commit()

# ✅ Must use flag_modified
from sqlalchemy.orm.attributes import flag_modified
config_row.config_json['tools']['enabled'].append('new_tool')
flag_modified(config_row, 'config_json')
session.commit()
```

---

## Related Documentation

- `/config_service/docs/TECH_SPEC.md` - API design
- `/config_service/docs/USING_CONFIG_SERVICE.md` - Usage guide
- `/docs/CONFIG_INHERITANCE.md` - Config inheritance

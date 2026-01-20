# Config Service - API Reference

REST API for configuration management and routing.

---

## Authentication

### Token Types

| Token Type | Format | Scope |
|------------|--------|-------|
| Global Admin | `env: ADMIN_TOKEN` | All orgs |
| Org Admin | `{org_id}.{random}` | Single org |
| Team | `{org_id}.{team_id}.{random}` | Single team |

### Headers

```
Authorization: Bearer <token>
```

---

## Endpoints

### GET /api/v1/auth/me

Get token identity.

**Response**:
```json
{
  "auth_kind": "team_token",
  "org_id": "extend",
  "team_node_id": "extend-sre"
}
```

---

### GET /api/v1/config/me/effective

Get effective configuration (with inheritance).

**Auth**: Team or Org Admin token

**Response**:
```json
{
  "agents": {...},
  "tools": {"enabled": [...], "disabled": [...]},
  "routing": {"slack_channel_ids": [...], ...},
  "integrations": {...}
}
```

---

### PUT /api/v1/config/me

Update team configuration.

**Auth**: Team or Org Admin token

**Body**:
```json
{
  "routing": {
    "slack_channel_ids": ["C123"],
    "services": ["payment"]
  },
  "integrations": {
    "coralogix": {
      "api_key": "cxup_...",
      "domain": "cx498.coralogix.com"
    }
  }
}
```

---

### POST /api/v1/internal/routing/lookup

Lookup team by routing identifiers.

**Auth**: Internal service header `X-Internal-Service: orchestrator`

**Body**:
```json
{
  "identifiers": {
    "slack_channel_id": "C0A4967KRBM"
  }
}
```

**Response**:
```json
{
  "found": true,
  "org_id": "extend",
  "team_node_id": "extend-sre",
  "matched_by": "slack_channel_id",
  "team_token": "extend.extend-sre...."
}
```

---

### POST /api/v1/admin/orgs

Create organization.

**Auth**: Global admin token

**Body**:
```json
{
  "org_id": "neworg",
  "name": "New Organization"
}
```

---

### POST /api/v1/admin/orgs/{org_id}/teams/{team_id}/tokens

Issue team token.

**Auth**: Global admin or Org admin token

**Body**:
```json
{
  "description": "Production token"
}
```

**Response**:
```json
{
  "token": "extend.extend-sre.J2KnE8rVmCfPWq...",
  "id": "uuid-here"
}
```

---

### GET /api/v1/agent-runs

List agent execution history.

**Auth**: Team or Org Admin token

**Query Parameters**:
- `limit` (default: 50)
- `offset` (default: 0)

**Response**:
```json
{
  "runs": [
    {
      "id": "uuid",
      "agent_name": "planner",
      "status": "success",
      "duration_seconds": 45.2,
      "created_at": "2026-01-12T10:30:00Z"
    }
  ],
  "total": 150
}
```

---

### GET /api/v1/integrations/health

Get integration health status.

**Auth**: Team or Org Admin token

**Response**:
```json
{
  "integrations": {
    "coralogix": {
      "status": "connected",
      "fields_configured": ["api_key", "domain"]
    },
    "slack": {
      "status": "not_configured",
      "missing_fields": ["bot_token"]
    }
  }
}
```

---

## Related Documentation

- `/config_service/docs/TECH_SPEC.md` - Design spec
- `/config_service/docs/DATABASE_SCHEMA.md` - Database schema
- `/docs/ROUTING_DESIGN.md` - Routing design

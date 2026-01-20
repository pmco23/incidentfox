# Orchestrator Architecture

> **Last Updated**: January 9, 2026

## Overview

The Orchestrator is the **control plane** for IncidentFox's multi-tenant AI SRE system.

### Control Plane vs Data Plane

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTROL PLANE (Orchestrator)                  │
│                                                                  │
│  • Team provisioning/deprovisioning workflows                    │
│  • K8s resource creation (CronJobs, Deployments)                │
│  • Cross-service coordination                                    │
│  • Provisioning audit trail                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Config Service  │  │ Agent Service   │  │ AI Pipeline     │
│ (Data Plane)    │  │ (Data Plane)    │  │ (Data Plane)    │
│                 │  │                 │  │                 │
│ • Team config   │  │ • Run agents    │  │ • Ingestion     │
│ • Routing       │  │ • Webhooks      │  │ • Learning      │
│ • Tokens        │  │ • Tools         │  │ • Evaluation    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### When Is Orchestrator Needed?

| Scenario | Use Orchestrator? | Why |
|----------|-------------------|-----|
| Create team + config | ❌ No | Call Config Service directly |
| Issue token | ❌ No | Call Config Service directly |
| Update routing | ❌ No | Call Config Service directly |
| Full provisioning with CronJob | ✅ Yes | Needs K8s API access |
| Deprovisioning with cleanup | ✅ Yes | Multi-service coordination |
| Create dedicated agent pod | ✅ Yes | K8s Deployment creation |

### Owns vs Delegates

| Owns (Infrastructure) | Delegates (Data) |
|----------------------|------------------|
| K8s CronJob creation | Team config → Config Service |
| K8s Deployment creation | Token management → Config Service |
| AI Pipeline triggers | Routing lookup → Config Service |
| Provisioning audit trail | Config audit → Config Service |
| Multi-service rollback | Agent execution → Agent Service |

## Endpoints

### Simple Operations: Call Config Service Directly

For pure data operations, clients should call Config Service:

```
# Create team node
POST /api/v1/admin/orgs/{org_id}/teams/{team_node_id}

# Set team config (including routing)
PUT /api/v1/admin/orgs/{org_id}/nodes/{node_id}/config

# Issue team token
POST /api/v1/admin/orgs/{org_id}/teams/{team_node_id}/tokens
```

### Full Provisioning: Call Orchestrator

When you need K8s resources + multi-service coordination:

```
POST /api/v1/admin/provision/team
{
  "org_id": "acme",
  "team_node_id": "platform-sre",
  "routing": {
    "slack_channel_ids": ["C0A4967KRBM"]
  },
  "create_pipeline_schedule": true
}
```

Orchestrator executes:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Call Config Service: create team node (if needed)           │
│ 2. Call Config Service: set routing config                      │
│ 3. Call Config Service: issue team token                        │
│ 4. Call K8s API: create CronJob for AI Pipeline  ← INFRA       │
│ 5. Call AI Pipeline: trigger bootstrap           ← COORDINATION │
│ 6. Record provisioning run for audit             ← AUDIT       │
└─────────────────────────────────────────────────────────────────┘
```

**Orchestrator's value**: Steps 4-6 (K8s, coordination, audit). Steps 1-3 could be called directly.

### Webhook Handling

**Orchestrator is the single entry point for all external webhooks.**

```
┌────────────────────────────────────────────────────────────────┐
│   Slack │ GitHub │ PagerDuty │ Incident.io │ Coralogix        │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                            │
│                                                                │
│  POST /webhooks/slack/events                                   │
│  POST /webhooks/github                                         │
│  POST /webhooks/pagerduty                                      │
│  POST /webhooks/incidentio                                     │
│                                                                │
│  For each webhook:                                             │
│  1. Verify signature (source-specific)                         │
│  2. Rate limit check                                           │
│  3. Routing lookup → Config Service                            │
│  4. Audit: log incoming event                                  │
│  5. Call Agent with team context                               │
│  6. Return response (ack to webhook source)                    │
└────────────────────────────────────────────────────────────────┘
```

**Why Orchestrator owns webhooks:**

| Reason | Explanation |
|--------|-------------|
| Single entry point | One place for all external events |
| Security | All webhook secrets in one service |
| Audit | Log every event before execution |
| Rate limiting | Prevent abuse, queue if needed |
| Routing | Centralized team lookup |
| Separation | "Receive event" ≠ "Execute agent" |

### 3. Agent Run Proxy (`POST /api/v1/admin/agents/run`)

Server-to-server agent invocation so team tokens never reach browsers:

```
Web UI (browser)
      │ Admin token
      ▼
Orchestrator
      │ Get impersonation token from Config Service
      │ Team token (short-lived)
      ▼
Agent Service
      │
      └── Returns result to Orchestrator → Web UI
```

## Data Model

### Tables (Shared Postgres)

```sql
-- Provisioning run tracking (audit trail)
CREATE TABLE orchestrator_provisioning_runs (
    id UUID PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128),
    status VARCHAR(32) NOT NULL,  -- running, succeeded, failed
    steps JSONB,                   -- Step-by-step progress
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Future: Pipeline schedules per team
CREATE TABLE orchestrator_pipeline_schedules (
    id UUID PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(64) NOT NULL,
    schedule_type VARCHAR(32) NOT NULL,  -- ingestion, gap_analysis, eval
    cron_expression VARCHAR(64) NOT NULL,
    k8s_cronjob_name VARCHAR(128),
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Routing Storage

**NOTE**: Routing identifiers (Slack channels, etc.) are stored in **Config Service** as part of team config, not in Orchestrator. This ensures single source of truth.

```json
// Stored in Config Service node_configurations table
{
  "routing": {
    "slack_channel_ids": ["C0A4967KRBM"],
    "incidentio_alert_source_ids": ["..."],
    "services": ["payment", "checkout"]
  }
}
```

Orchestrator writes routing config to Config Service during provisioning. Agent reads it via Config Service `/api/v1/internal/routing/lookup`.

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Shared Postgres connection string |
| `CONFIG_SERVICE_URL` | Config Service base URL |
| `AI_PIPELINE_API_URL` | AI Pipeline API base URL |
| `AGENT_API_URL` | Agent Service base URL |
| `ORCHESTRATOR_INTERNAL_TOKEN` | Shared secret for internal service calls |
| `ORCHESTRATOR_INTERNAL_ADMIN_TOKEN` | Admin token for impersonation |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORCHESTRATOR_AUTO_CREATE_TABLES` | `0` | Auto-create tables on startup (dev only) |
| `ORCHESTRATOR_ADMIN_AUTH_CACHE_TTL_SECONDS` | `15` | Cache TTL for admin auth |
| `ORCHESTRATOR_REQUIRE_ADMIN_STAR` | `1` | Require admin:* permission |
| `ORCHESTRATOR_SLACK_AGENT_TIMEOUT_SECONDS` | `300` | Agent timeout for Slack triggers |
| `ORCHESTRATOR_SLACK_AGENT_MAX_TURNS` | `50` | Max agent turns for Slack triggers |

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check |
| `GET` | `/metrics` | None | Prometheus metrics |
| `POST` | `/api/v1/admin/provision/team` | Admin token | Provision a team |
| `GET` | `/api/v1/admin/provision/runs/{id}` | Admin token | Get provisioning status |
| `POST` | `/api/v1/admin/agents/run` | Admin token | Run agent for team |
| `POST` | `/api/v1/internal/slack/trigger` | Internal token | Internal Slack routing |

## Concurrency & Idempotency

### Advisory Locks

Provisioning uses Postgres advisory locks to prevent races across replicas:

```python
# Lock key: (org_id, team_node_id)
conn.execute("SELECT pg_advisory_lock(hashtext(:k))", {"k": lock_key})
try:
    # ... provisioning logic ...
finally:
    conn.execute("SELECT pg_advisory_unlock(hashtext(:k))", {"k": lock_key})
```

### Idempotency Keys

Callers can pass `idempotency_key` in provisioning requests:

```json
{
  "org_id": "acme",
  "team_node_id": "platform-sre",
  "idempotency_key": "provision-2024-01-09-abc123"
}
```

If a run with the same key exists, the original result is returned.

## Integration with Other Services

```
┌─────────────────────────────────────────────────────────────────┐
│                        Orchestrator                              │
└───────┬─────────────────┬─────────────────┬─────────────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│Config Service │ │ Agent Service │ │ AI Pipeline   │
├───────────────┤ ├───────────────┤ ├───────────────┤
│ - Auth verify │ │ - Run agents  │ │ - Bootstrap   │
│ - Team tokens │ │ - Webhooks    │ │ - Ingestion   │
│ - Config CRUD │ │               │ │ - Evals       │
└───────────────┘ └───────────────┘ └───────────────┘
```

## Related Documentation

- [MULTI_TENANT_DESIGN.md](./MULTI_TENANT_DESIGN.md) - Multi-tenancy architecture options
- [../README.md](../README.md) - Quick start and MVP overview
- [../../docs/ROUTING_DESIGN.md](../../docs/ROUTING_DESIGN.md) - Webhook routing design


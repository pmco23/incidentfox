# `orchestrator/` — Team Onboarding + Provisioning Control Plane

This subsystem is the **control plane** for IncidentFox's multi-tenant AI SRE system.

## What It Does

### Webhook Handling (All External Events)
- Receives and verifies all external webhooks: **Slack, GitHub, PagerDuty, Incident.io**
- Performs signature verification for each source
- Routes events to the correct team via Config Service lookup
- Triggers agent runs with team context

### Team Provisioning
- Provisions **team configuration** in Config Service (routing, prompts, tools)
- Issues **team authentication tokens**
- Creates **AI Pipeline CronJobs** for scheduled learning
- Creates **dedicated agent Deployments** for enterprise teams

### Kubernetes Operations
- Creates K8s **CronJobs** for AI Pipeline scheduling
- Creates K8s **Deployments + Services** for dedicated agent pods
- Manages lifecycle of team-specific K8s resources

> **Status**: Production-ready (FastAPI + webhooks + K8s integration)

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [docs/NORTH_STAR.md](docs/NORTH_STAR.md) | **Target architecture - READ THIS FIRST** |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Current architecture, endpoints, data model |
| [docs/MULTI_TENANT_DESIGN.md](docs/MULTI_TENANT_DESIGN.md) | Multi-tenancy options and roadmap |
| [../docs/ROUTING_DESIGN.md](../docs/ROUTING_DESIGN.md) | Webhook routing design |
| [../docs/ARCHITECTURE_DECISIONS.md](../docs/ARCHITECTURE_DECISIONS.md) | Key ADRs and rationale |

## Endpoints

### Webhook Endpoints

All external webhooks should be pointed to these endpoints:

| Path | Source | Auth |
|------|--------|------|
| `POST /webhooks/slack/events` | Slack Events API | X-Slack-Signature |
| `POST /webhooks/slack/interactions` | Slack Interactivity | X-Slack-Signature |
| `POST /webhooks/github` | GitHub Webhooks | X-Hub-Signature-256 |
| `POST /webhooks/pagerduty` | PagerDuty V3 | X-PagerDuty-Signature |
| `POST /webhooks/incidentio` | Incident.io | X-Incident-Signature |

### Admin Endpoints

| Path | Purpose |
|------|---------|
| `POST /api/v1/admin/provision/team` | Full team provisioning |
| `GET /api/v1/admin/provision/runs/{run_id}` | Get provisioning status |
| `POST /api/v1/admin/agents/run` | Admin-triggered agent run |

### What "provision team" does

Given `{ org_id, team_node_id, slack_channel_ids[], pipeline_schedule?, deployment_mode? }`:
1. Patches team config in Config Service with routing hints
2. Issues team token (returned once)
3. Triggers AI Pipeline bootstrap
4. **(NEW)** Creates AI Pipeline CronJob if `pipeline_schedule` provided
5. **(NEW)** Creates dedicated Deployment/Service if `deployment_mode=dedicated`

#### Idempotency + concurrency (production-ready MVP)

- **Concurrency safety**: provisioning uses a **Postgres advisory lock** keyed by `(org_id, team_node_id)` held for the duration of the request, so multiple replicas won’t race.
- **Idempotency**: callers may pass `idempotency_key` in the request body; repeated calls with the same key will return the same `provisioning_run_id` and status (without re-running side effects).

### Required configuration (env)

- `CONFIG_SERVICE_URL`: base URL for `config_service` (for admin verification and provisioning calls)
- `AI_PIPELINE_API_URL`: base URL for `ai_pipeline` HTTP API
- `AGENT_API_URL`: base URL for `agent` HTTP API
- `DATABASE_URL` (or `DB_HOST`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`): shared Postgres
- `ORCHESTRATOR_AUTO_CREATE_TABLES=1` (local dev only): allow orchestrator to create its tables on startup.

**Webhook Secrets** (for signature verification):
- `SLACK_SIGNING_SECRET`: Slack app signing secret
- `GITHUB_WEBHOOK_SECRET`: GitHub webhook secret
- `PAGERDUTY_WEBHOOK_SECRET`: PagerDuty webhook secret
- `INCIDENTIO_WEBHOOK_SECRET`: Incident.io webhook secret

**Agent Response** (for posting back to Slack):
- `SLACK_BOT_TOKEN`: Slack bot token for posting results
- `ORCHESTRATOR_INTERNAL_ADMIN_TOKEN`: Admin token for issuing impersonation tokens

**K8s Operations** (for CronJobs and Deployments):
- `K8S_NAMESPACE`: Kubernetes namespace (default: `incidentfox`)
- `AI_PIPELINE_IMAGE`: Docker image for AI Pipeline CronJobs
- `AGENT_IMAGE`: Docker image for dedicated agent Deployments

Optional:
- `ORCHESTRATOR_ADMIN_AUTH_CACHE_TTL_SECONDS`: small in-memory cache TTL for config_service admin verification (default: 15s).
- `ORCHESTRATOR_REQUIRE_ADMIN_STAR=1`: require `admin:*` in the principal permissions (default: 1).
- **Endpoint-scoped permissions** (defaults shown):
  - `ORCHESTRATOR_REQUIRED_PERMISSION_PROVISION_TEAM=admin:provision`
  - `ORCHESTRATOR_REQUIRED_PERMISSION_PROVISION_READ=admin:provision:read`
  - `ORCHESTRATOR_REQUIRED_PERMISSION_AGENT_RUN=admin:agent:run`

In production, we do **not** auto-create tables on boot. Apply schema changes via a controlled migration step (TBD: Alembic), or explicitly enable auto-create only for ephemeral dev environments.

## Responsibilities

### 1) Team onboarding workflow

On “create team” (or “enable IncidentFox for team”):
- create the team identity + default config in `config_service/`
- issue or register team auth (team token / OIDC policy)
- initialize knowledge base namespace (empty or seeded)
- start/provision:
  - agent runtime (always-on listener or on-demand runner)
  - AI pipeline schedules (EventBridge/ECS tasks or equivalent)

### 2) Provisioning + lifecycle

- Create/update/destroy per-team runtime resources:
  - ECS services/tasks, schedules, queues, etc. (implementation detail)
- Track desired vs actual state (idempotent reconcile loop)
- Support upgrades/rollbacks by switching which “release” is active for a team

### 3) Governance glue

Orchestrator doesn’t decide content (prompts/tools) — it enforces **where/when** a team runs:
- ensure “write tools” remain disabled unless approved
- ensure audit/logging sinks are configured
- ensure data locality constraints (in-VPC) are enforced by deployment topology

## How it integrates with other subsystems

- **`config_service/`**:
  - stores team/org model and effective config
  - stores proposal/approval metadata (roadmap) and “active releases”
- **`ai_pipeline/`**:
  - runs per-team jobs and stores proposals/eval artifacts
  - updates/publishes knowledge base artifacts for the team
- **`knowledge_base/`**:
  - per-team namespace (trees/indices)
  - produces retrieval evidence for agents/UI
- **`agent/`**:
  - per-team runtime that reads effective config and queries KB
  - emits traces/tool calls/audit events
- **`web_ui/`**:
  - surfaces onboarding status, runtime health, evals, traces, KB, and diffs/approvals
- **`database/`**:
  - shared persistence layer (audit/events/runs/evals), plus infra/tunnels

## Data Model

### Current Tables (Shared Postgres)

```sql
-- Slack channel to team mapping
CREATE TABLE orchestrator_team_slack_channels (
    slack_channel_id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(64) NOT NULL
);

-- Provisioning run tracking
CREATE TABLE orchestrator_provisioning_runs (
    id UUID PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    team_node_id VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128),
    status VARCHAR(32) NOT NULL,
    steps JSONB,
    error TEXT
);
```

### Future Tables (see [docs/MULTI_TENANT_DESIGN.md](docs/MULTI_TENANT_DESIGN.md))

- `team_runtimes` - Track per-team deployment state
- `pipeline_schedules` - Per-team AI Pipeline CronJobs
- `runtime_events` - Provisioning actions audit log

## Development

```bash
cd orchestrator

# Install dependencies
pip install -e .

# Run locally
python -m incidentfox_orchestrator

# Run tests
pytest

# Build Docker
docker build -t incidentfox-orchestrator .
```

## Related Services

- **Config Service** - Team configuration, tokens, routing lookup
- **Agent Service** - Runs AI agents (shared runtime)
- **AI Pipeline** - Per-team learning jobs
- **Web UI** - Admin console for provisioning


# Architecture Decisions

> **Last Updated**: January 9, 2026
> **Purpose**: Document key architectural decisions and their rationale

---

## ADR-001: Shared Agent Runtime vs Per-Team Pods

**Status**: Decided (Shared Runtime with future per-team option)

### Context

When serving multiple teams, we need to decide how to isolate agent execution:
- All teams share one agent deployment, or
- Each team gets dedicated pods

### Decision

**Start with shared runtime**, add per-team pods as premium enterprise feature.

### Rationale

1. **Simplicity**: Shared runtime is easier to operate and monitor
2. **Cost**: Per-team pods multiply infrastructure costs linearly
3. **Latency**: No cold start with shared runtime
4. **Soft isolation sufficient**: Per-request config loading with resource quotas covers 95% of use cases

### Consequences

- Team isolation is configuration-based, not infrastructure-based
- Need rate limiting and quotas per team to prevent noisy neighbors
- Enterprise customers needing hard isolation will need dedicated pods (future)

### Related

- [orchestrator/docs/MULTI_TENANT_DESIGN.md](../orchestrator/docs/MULTI_TENANT_DESIGN.md)

---

## ADR-002: Webhook Routing via Config Service

**Status**: Decided (consolidate routing in Config Service)

### Context

When webhooks arrive (Slack, Incident.io, PagerDuty, GitHub), we need to identify which team should handle them. Currently routing is split:
- `orchestrator_team_slack_channels` table (Orchestrator)
- `routing` JSON in team config (Config Service)
- `/api/v1/internal/routing/lookup` endpoint (Config Service)

### Decision

**Consolidate all routing in Config Service**. Remove `orchestrator_team_slack_channels` table.

### Rationale

1. **Single source of truth**: All team config in one place
2. **Already implemented**: Config Service has `/routing/lookup` endpoint
3. **Extensible**: Routing config supports Slack, Incident.io, PagerDuty, GitHub, services
4. **Validation**: Config Service can enforce uniqueness per-org

### Consequences

- Orchestrator no longer stores Slack mappings directly
- During provisioning, Orchestrator updates routing config via Config Service
- Agent service calls Config Service for routing lookup
- Simpler mental model

### Related

- [docs/ROUTING_DESIGN.md](./ROUTING_DESIGN.md)

---

## ADR-003: Orchestrator Owns All Webhooks

**Status**: Decided (Orchestrator handles all external webhooks)

### Context

Webhooks are currently duplicated across services:
- Web UI: `/api/slack/events`, `/api/github/webhook`, `/api/pagerduty/webhook`
- Agent: `/webhooks/slack/events`, `/webhooks/github`, `/webhooks/pagerduty`, `/webhooks/incidentio`
- Orchestrator: `/api/v1/internal/slack/trigger` (internal)

This is a mess with three different patterns.

### Decision

**Orchestrator handles all external webhooks**. Web UI and Agent webhook handlers are removed.

```
Webhook → Orchestrator → Routing (Config Service) → Agent → Audit (Config Service)
```

### Rationale

| Reason | Explanation |
|--------|-------------|
| Single entry point | One place for all external events |
| Security | All webhook secrets in one service, easy rotation |
| Audit/Compliance | Log every event before execution (SOC2, GDPR) |
| Rate limiting | Prevent abuse, queue if overloaded |
| Separation | "Receive event" ≠ "Execute agent" |
| Routing | Centralized team lookup via Config Service |

### Webhook Flow

```
┌─────────────────────────────────────────────────────────────────┐
│   Slack │ GitHub │ PagerDuty │ Incident.io │ Custom            │
└────────────────────────────────┬────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                             │
│  1. Verify signature (per-source)                               │
│  2. Rate limit check                                            │
│  3. Routing lookup → Config Service                             │
│  4. Audit: log incoming event                                   │
│  5. Trigger Agent run with team context                         │
│  6. Agent posts results (Slack/GitHub/etc)                      │
└─────────────────────────────────────────────────────────────────┘
```

### Consequences

**To Implement:**
- Move webhook handlers from Agent to Orchestrator
- Remove Web UI webhook handlers
- Orchestrator needs: Slack, GitHub, PagerDuty, Incident.io signature verification
- Agent exposes simple `/api/v1/run` endpoint (no webhooks)

**Latency:**
- Extra hop adds ~10-50ms
- Acceptable for enterprise requirements (audit, security)

### Related

- [orchestrator/docs/ARCHITECTURE.md](../orchestrator/docs/ARCHITECTURE.md)

---

## ADR-004: Orchestrator as Control Plane (Enterprise Design)

**Status**: Decided

### Context

For an enterprise product, clear separation between control plane and data plane is critical:
- Config Service should be the single source of truth for all team data
- Clients should be able to call Config Service directly for CRUD operations
- Orchestrator should only be needed for infrastructure/coordination

### Decision

**Config Service handles all data operations directly. Orchestrator handles infrastructure and multi-service coordination.**

### Who Calls What

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Clients                                         │
│            (Web UI, Admin CLI, External Systems)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                           │
                    │ Data Operations           │ Infra Operations
                    │ (direct)                  │ (workflows)
                    ▼                           ▼
┌─────────────────────────────┐    ┌─────────────────────────────┐
│       Config Service        │    │       Orchestrator          │
│       (Data Plane)          │    │     (Control Plane)         │
└─────────────────────────────┘    └─────────────────────────────┘
```

### Config Service (Data Plane) - Direct Access

Clients call Config Service directly for:
- Create/update team nodes
- Set/get team configuration
- Issue/revoke tokens
- Routing lookup
- Audit logs

### Orchestrator (Control Plane) - Infrastructure Only

Orchestrator is called when:
- K8s resources needed (CronJobs, Deployments)
- Multi-service coordination (Config + Pipeline + KB)
- Complex workflows with rollback
- Full provisioning (convenience wrapper)

### When to Use Which

| Operation | Call | Why |
|-----------|------|-----|
| Create team + config + token | Config Service | Pure data operation |
| Full provisioning with CronJob | Orchestrator | Needs K8s API |
| Update team config | Config Service | Pure data operation |
| Deprovisioning with cleanup | Orchestrator | Multi-service + K8s |
| Routing lookup | Config Service | Runtime data lookup |

### Rationale

1. **Config Service shouldn't have K8s access** - security principle
2. **Clients shouldn't need Orchestrator for CRUD** - simplicity
3. **Orchestrator adds value only for infrastructure** - clear purpose
4. **Both are stateless** - Config Service stores data in Postgres

### Related

- [orchestrator/docs/ARCHITECTURE.md](../orchestrator/docs/ARCHITECTURE.md)
- [orchestrator/docs/MULTI_TENANT_DESIGN.md](../orchestrator/docs/MULTI_TENANT_DESIGN.md)

---

## ADR-005: Database Strategy (Shared vs Per-Service)

**Status**: Decided (Shared Postgres with service-prefixed tables)

### Context

Should each service have its own database, or share one?

### Decision

**Shared Postgres database** with service-prefixed tables.

### Current Tables

| Service | Tables |
|---------|--------|
| Config Service | `org_nodes`, `node_configurations`, `team_tokens`, `org_admin_tokens`, `agent_runs` |
| Orchestrator | `orchestrator_team_slack_channels`, `orchestrator_provisioning_runs` |
| AI Pipeline | `ai_pipeline_*` (future) |

### Rationale

1. **Simplicity**: One RDS instance to manage
2. **Cost**: Fewer database instances
3. **Transactions**: Cross-service queries possible if needed
4. **Isolation**: Table prefixes provide logical separation

### Consequences

- Schema migrations need coordination
- Connection pool shared across services
- Future: May need to split if scale requires it

---

## ADR-006: Agent Configuration Loading

**Status**: Decided (Dynamic from Config Service)

### Context

How should agents get their configuration (prompts, tools, sub-agents)?

Options:
1. Hardcoded in Python classes
2. YAML/JSON files in repo
3. Dynamic from Config Service per request

### Decision

**Dynamic loading from Config Service** via `get_planner_for_team()`.

### Rationale

1. **Per-team customization**: Each team can have different prompts
2. **Hot reload**: Config changes don't require redeploy
3. **Governance**: Config Service handles approvals
4. **Audit trail**: Config changes tracked

### Implementation

```python
from ai_agent.core.config_loader import get_planner_for_team

# Load team-specific agent configuration
planner = get_planner_for_team(org_id="acme", team_node_id="platform-sre")
result = await Runner.run(planner, "Investigate high latency")
```

### Related

- [agent/docs/DYNAMIC_AGENT_SYSTEM.md](../agent/docs/DYNAMIC_AGENT_SYSTEM.md)

---

## ADR-007: AI Pipeline Scheduling

**Status**: Proposed

### Context

Each team needs periodic AI Pipeline jobs:
- Ingestion (pull from Slack, tickets, etc.)
- Gap analysis (identify missing tools/knowledge)
- Evaluation (test agent performance)

### Decision

**Orchestrator creates K8s CronJobs per team** during provisioning.

### Design

```yaml
# Created by Orchestrator on team provision
apiVersion: batch/v1
kind: CronJob
metadata:
  name: incidentfox-pipeline-${team_id}
spec:
  schedule: "0 2 * * *"  # Daily at 2am
  jobTemplate:
    spec:
      containers:
      - name: pipeline
        image: ${pipeline_image}
        env:
        - name: TEAM_ID
          value: ${team_id}
        command: ["python", "-m", "ai_learning_pipeline.scripts.run_orchestrator"]
```

### Alternatives Considered

1. **EventBridge (AWS)**: Good for serverless, but K8s-native is simpler in EKS
2. **In-process scheduler**: Less observable, harder to manage per-team
3. **Single shared CronJob**: Doesn't scale with many teams

### Status

Not yet implemented. Track in [orchestrator/docs/MULTI_TENANT_DESIGN.md](../orchestrator/docs/MULTI_TENANT_DESIGN.md).

---

## Summary

| ADR | Decision | Status |
|-----|----------|--------|
| 001 | Shared agent runtime (per-team pods as premium) | ✅ Decided |
| 002 | All routing via Config Service | ✅ Decided |
| 003 | Agent handles all webhooks | ✅ Decided |
| 004 | Orchestrator = control plane for lifecycle | ✅ Decided |
| 005 | Shared Postgres with service-prefixed tables | ✅ Decided |
| 006 | Dynamic agent config from Config Service | ✅ Decided |
| 007 | K8s CronJobs per team for AI Pipeline | 📋 Proposed |


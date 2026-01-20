# Orchestrator North Star Architecture

> **Last Updated**: January 10, 2026
> **Status**: Target architecture for enterprise product
> **Purpose**: Guide implementation decisions

---

## 🚀 Multi-Tenancy Support

IncidentFox supports two agent deployment modes:

- **Shared Runtime** (default): All teams share agent pods, cost-effective
- **Dedicated Pods** (enterprise): Teams get isolated deployments with custom resources

See: `/docs/MULTI_TENANT_DESIGN.md` for detailed comparison, cost analysis, and provisioning procedures

---

## 🎯 Core Principles

### 1. Clear Service Boundaries

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CONFIG SERVICE                                  │
│                            (Data Plane - CRUD)                              │
│                                                                              │
│  • Team/org hierarchy                    • Direct client access              │
│  • Team configuration (prompts, tools)   • Routing lookup                    │
│  • Tokens (issue, revoke, validate)      • Audit logs (config + runs)       │
│  • Effective config computation          • No infrastructure ops            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATOR                                    │
│                     (Control Plane - Workflows + Webhooks)                  │
│                                                                              │
│  • All external webhooks                 • K8s resource creation             │
│  • Routing lookup (calls Config Svc)     • AI Pipeline scheduling           │
│  • Agent run triggering                  • Provisioning workflows           │
│  • Rate limiting                         • Audit (incoming events)          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              AGENT SERVICE                                   │
│                          (Data Plane - Execution)                           │
│                                                                              │
│  • Run agents (planner, investigation)   • No webhook handling              │
│  • Execute tools (K8s, AWS, etc)         • No routing logic                 │
│  • Post results (Slack, GitHub)          • Called by Orchestrator only      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Data Operations → Config Service (Direct)

Clients can call Config Service directly for all data operations:

```
# Team management
POST   /api/v1/admin/orgs/{org}/teams/{team}        # Create team
PUT    /api/v1/admin/orgs/{org}/nodes/{node}/config # Update config
DELETE /api/v1/admin/orgs/{org}/teams/{team}        # Delete team

# Tokens
POST   /api/v1/admin/orgs/{org}/teams/{team}/tokens # Issue token
DELETE /api/v1/admin/orgs/{org}/teams/{team}/tokens/{id} # Revoke

# Runtime
GET    /api/v1/config/me/effective                  # Get team config
POST   /api/v1/internal/routing/lookup              # Routing lookup
```

### 3. External Events → Orchestrator (Single Entry Point)

All webhooks go to Orchestrator:

```
POST /webhooks/slack/events      # Slack @mentions
POST /webhooks/slack/interactions # Slack buttons
POST /webhooks/github            # GitHub comments, CI failures
POST /webhooks/pagerduty         # PagerDuty alerts
POST /webhooks/incidentio        # Incident.io incidents
POST /webhooks/generic           # Custom webhooks
```

### 4. Infrastructure Operations → Orchestrator

K8s resources, multi-service coordination:

```
POST   /api/v1/admin/provision/team     # Full provisioning (config + K8s)
DELETE /api/v1/admin/provision/team     # Deprovisioning + cleanup
POST   /api/v1/admin/schedules/team     # Create pipeline CronJob
POST   /api/v1/admin/agents/run         # Admin-triggered agent run
```

---

## 🏗️ Target Request Flows

### Webhook Flow (Slack/GitHub/PagerDuty/Incident.io)

```
1. External Source → Orchestrator (webhook endpoint)
2. Orchestrator: Verify signature
3. Orchestrator: Rate limit check (TODO)
4. Orchestrator → Source: Return 200 OK (async processing)
5. Orchestrator → Config Service: Routing lookup
6. Orchestrator: Log incoming event (audit)
7. Orchestrator → Agent: Run agent with team context + slack_context
8. Agent: Post initial "working" message to Slack (Block Kit)
9. Agent: Execute investigation, use tools
10. Agent: Update Slack with progress (real-time)
11. Agent: Post final results to Slack (rich Block Kit)
12. Orchestrator → Config Service: Save agent run audit
```

### Slack Output Pattern (Agent-Direct)

The Agent now posts results directly to Slack instead of returning to Orchestrator:

```
Orchestrator                           Agent                              Slack
    │                                    │                                  │
    │  POST /agents/planner/run          │                                  │
    │  + slack_context: {                │                                  │
    │      channel_id, thread_ts,        │                                  │
    │      user_id                       │                                  │
    │    }                               │                                  │
    │─────────────────────────────────▶  │                                  │
    │                                    │  chat.postMessage (initial)      │
    │                                    │─────────────────────────────────▶│
    │                                    │                                  │
    │                                    │  (runs tools, updates progress)  │
    │                                    │                                  │
    │                                    │  chat.update (progress)          │
    │                                    │─────────────────────────────────▶│
    │                                    │                                  │
    │                                    │  chat.update (final result)      │
    │                                    │─────────────────────────────────▶│
    │                                    │                                  │
    │  {"success": true,                 │                                  │
    │   "output_mode": "slack_direct"}   │                                  │
    │◀─────────────────────────────────  │                                  │
```

**Why Agent-Direct?**
- Real-time progress updates as phases complete
- Rich Block Kit UI with structured output
- Agent already has the rendering logic (`slack_ui.py`, `slack_output.py`)
- Single responsibility: Orchestrator routes, Agent outputs

### Direct Team Config Update

```
1. Web UI → Config Service: PUT /api/v1/admin/orgs/{org}/nodes/{node}/config
2. Config Service: Validate, save, audit
3. Config Service → Web UI: Return updated config
```

### Full Team Provisioning

```
1. Web UI → Orchestrator: POST /api/v1/admin/provision/team
2. Orchestrator → Config Service: Create team node
3. Orchestrator → Config Service: Set routing config
4. Orchestrator → Config Service: Issue team token
5. Orchestrator → K8s API: Create CronJob for AI Pipeline
6. Orchestrator → AI Pipeline: Trigger bootstrap
7. Orchestrator: Record provisioning run (audit)
8. Orchestrator → Web UI: Return success + token
```

---

## 📋 Implementation Status

### Phase 1: Consolidate Webhooks to Orchestrator ✅ COMPLETED

- [x] Add webhook endpoints to Orchestrator:
  - [x] `/webhooks/slack/events` - Full signature verification
  - [x] `/webhooks/slack/interactions` - Signature verification
  - [x] `/webhooks/github` - X-Hub-Signature-256 verification
  - [x] `/webhooks/pagerduty` - X-PagerDuty-Signature verification
  - [x] `/webhooks/incidentio` - X-Incident-Signature verification
- [x] Port signature verification logic from Agent/Web UI (`webhooks/signatures.py`)
- [x] Add routing lookup (call Config Service `/api/v1/internal/routing/lookup`)
- [x] Add audit logging for incoming events
- [ ] **TODO**: Test with real webhooks (point test channel to new endpoints)
- [ ] **TODO**: Gradually migrate external webhook URLs to Orchestrator

### Phase 2: Clean Up Duplicates ✅ COMPLETED

- [x] Mark Agent webhook endpoints as deprecated (log warnings)
- [x] Mark Web UI webhook endpoints as deprecated
- [x] Updated Slack trigger to use Config Service routing (with fallback)
- [ ] **TODO**: After 1 release cycle, remove deprecated endpoints
- [ ] **TODO**: Remove `orchestrator_team_slack_channels` table (migration)

### Phase 3: AI Pipeline Scheduling ✅ COMPLETED

- [x] Add K8s client to Orchestrator (`kubernetes>=29.0.0` in pyproject.toml)
- [x] Implement CronJob creation (`k8s/cronjobs.py`)
- [x] Implement CronJob deletion
- [x] Integrate CronJob creation into provisioning endpoint
- [ ] **TODO**: Add `/api/v1/admin/schedules/team` endpoint for manual schedule updates

### Phase 4: Dedicated Pods (Enterprise Feature) ✅ COMPLETED

- [x] Add `deployment_mode` field to ProvisionRequest
- [x] Implement K8s Deployment creation (`k8s/deployments.py`)
- [x] Implement K8s Service creation
- [x] Update all webhook handlers to use dedicated agent URL when configured
- [x] Store `dedicated_service_url` in team config after provisioning
- [ ] **TODO**: Implement dedicated pod cleanup during deprovisioning
- [ ] **TODO**: Add resource limits configuration UI

### Phase 5: Simplify Agent ✅ COMPLETED

- [x] Agent receives team context from Orchestrator (via X-IncidentFox-Team-Token)
- [x] Keep existing endpoints working (backwards compatibility)
- [x] Agent posts results directly to Slack via `slack_context` parameter
- [x] New file: `agent/src/ai_agent/core/slack_output.py` - Generalized Slack Block Kit output
- [ ] **TODO**: Add clean `/api/v1/run` endpoint (standardized interface)

### Phase 6: Cleanup Tech Debt ✅ COMPLETE (2026-01-10)

- [x] Removed `_post_slack_result()` from Orchestrator (TD-001)
- [x] Removed deprecated `/api/v1/internal/slack/trigger` endpoint (TD-002)
- [x] Removed Agent webhook endpoints (TD-003) - file reduced 2461 → 838 lines
- [x] Removed Web UI `/api/slack/events/route.ts` (TD-004)
- [x] Removed Web UI `/api/github/webhook/route.ts`
- [x] Removed Web UI `/api/pagerduty/webhook/route.ts`
- [x] Added migration `003_drop_team_slack_channels` to drop table (TD-005)
- [x] Removed `TeamSlackChannel` model from `models.py`

**Completed**: 2026-01-10

---

## 🔐 Security Model

### Secrets Distribution

| Secret | Stored In | Accessed By |
|--------|-----------|-------------|
| Slack signing secret | Orchestrator | Orchestrator |
| Slack bot token | Orchestrator + Agent | Orchestrator (webhook ack), Agent (post results) |
| GitHub webhook secret | Orchestrator | Orchestrator |
| GitHub token | Agent | Agent (post comments, reactions) |
| PagerDuty webhook secret | Orchestrator | Orchestrator |
| Incident.io webhook secret | Orchestrator | Orchestrator |
| OpenAI API key | Agent | Agent |
| Database URL | Config Service, Orchestrator | Both |
| K8s API access | Orchestrator | Orchestrator (CronJobs, Deployments) |

### Authentication

| Endpoint | Auth Method |
|----------|-------------|
| Config Service admin endpoints | Admin token (org-scoped) |
| Config Service team endpoints | Team token |
| Config Service internal endpoints | X-Internal-Service header |
| Orchestrator admin endpoints | Admin token (via Config Service) |
| Orchestrator webhooks | Source-specific signature |
| Agent `/api/v1/run` | Team token (from Orchestrator) |

---

## 📊 Endpoint Summary

### Config Service (Data Plane)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/v1/admin/orgs/{org}/teams/{team}` | Admin | Create team |
| PUT | `/api/v1/admin/orgs/{org}/nodes/{node}/config` | Admin | Update config |
| POST | `/api/v1/admin/orgs/{org}/teams/{team}/tokens` | Admin | Issue token |
| GET | `/api/v1/config/me/effective` | Team | Get effective config |
| POST | `/api/v1/internal/routing/lookup` | Internal | Routing lookup |
| POST | `/api/v1/internal/agent-runs` | Internal | Record agent run |

### Orchestrator (Control Plane)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/webhooks/slack/events` | Slack signature | Slack @mentions |
| POST | `/webhooks/github` | GitHub signature | GitHub comments |
| POST | `/webhooks/pagerduty` | PagerDuty signature | PagerDuty alerts |
| POST | `/webhooks/incidentio` | Incident.io signature | Incidents |
| POST | `/api/v1/admin/provision/team` | Admin | Full provisioning |
| DELETE | `/api/v1/admin/provision/team` | Admin | Deprovisioning |
| POST | `/api/v1/admin/agents/run` | Admin | Admin agent run |

### Agent (Execution)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/v1/run` | Team token | Run agent |
| GET | `/health` | None | Health check |
| GET | `/metrics` | None | Prometheus metrics |

---

## ⚠️ Anti-Patterns to Avoid

1. **Don't duplicate routing storage** - Config Service is single source of truth
2. **Don't handle webhooks in multiple places** - Orchestrator only
3. **Don't call Agent directly from external sources** - Always through Orchestrator
4. **Don't store team config in Orchestrator** - That's Config Service's job
5. **Don't give Agent K8s API access** - That's Orchestrator's job
6. **Don't give Config Service K8s API access** - Data plane only
7. **Don't break existing endpoints** - Add new, deprecate old, then remove

---

## 🎯 Success Criteria

This architecture is successful when:

1. ✅ All webhooks have single entry point (Orchestrator)
2. ✅ All team data in single place (Config Service)
3. ✅ K8s operations in single place (Orchestrator)
4. ✅ Agent is stateless executor (no routing, no webhooks)
5. ✅ Clear audit trail for all events
6. ✅ Web UI only calls Config Service for CRUD
7. ✅ No duplicate data storage


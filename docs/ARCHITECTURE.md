# IncidentFox - System Architecture

High-level system design and service interactions.

---

## Service Overview

```
External Services (Slack, GitHub, PagerDuty)
    ↓ webhooks
AWS API Gateway (on3vboii0g)
    ↓ HTTPS
ALB (k8s-incident-...)
    ↓
┌─────────────────────────────────────────────────────────┐
│  Kubernetes Cluster (incidentfox-demo)                  │
│  Namespace: incidentfox                                 │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐   ┌──────────┐  │
│  │ Orchestrator │───▶│ Config       │   │ Web UI   │  │
│  │ - Routing    │    │ Service      │   │ (Next.js)│  │
│  │ - Auth       │    │ - DB         │   │          │  │
│  └──────┬───────┘    │ - Tokens     │   └──────────┘  │
│         │            └──────────────┘                  │
│         ▼                                               │
│  ┌──────────────┐                                      │
│  │ Agent        │                                      │
│  │ - OpenAI SDK │                                      │
│  │ - Tools      │                                      │
│  │ - MCPs       │                                      │
│  └──────────────┘                                      │
│                                                          │
│  ┌──────────────┐                                      │
│  │ SRE Agent    │                                      │
│  │ - Claude SDK │                                      │
│  │ - Sandboxes  │                                      │
│  └──────────────┘                                      │
└─────────────────────────────────────────────────────────┘
    ↓
External Services (Slack, Datadog, Coralogix, etc.)
```

---

## Request Flow

### Webhook Flow (Slack @mention)

```
1. User @mentions IncidentFox in Slack channel C0A4967KRBM
2. Slack → AWS API Gateway → ALB → Orchestrator
3. Orchestrator:
   a. Verify signature
   b. Return 200 OK (< 3 seconds)
   c. Extract routing identifier (slack_channel_id)
   d. Lookup team via Config Service
   e. Get impersonation token
4. Orchestrator → Agent: POST /api/v1/agent/run
5. Agent:
   a. Post "🔍 Investigating..." to Slack
   b. Run planner → delegates to sub-agents
   c. Execute tools (Coralogix, Snowflake, K8s, etc.)
   d. Update Slack with progress
   e. Post final RCA and recommendations
```

See: `/orchestrator/docs/WEBHOOKS.md` for details.

---

## Data Flow

### Configuration Hierarchy

```
Organization (extend)
  ├── Config: {agents, tools, integrations}
  ├── Unit (platform)
  │   ├── Config: inherits + overrides
  │   └── Team (platform-sre)
  │       └── Config: inherits + overrides
  └── Team (customer-success)
      └── Config: inherits + overrides
```

**Effective Config** = Org config + Unit overrides + Team overrides

See: `/docs/CONFIG_INHERITANCE.md`

---

## Authentication & Authorization

### Token Types

| Type | Format | Scope | Used By |
|------|--------|-------|---------|
| Global Admin | `env: ADMIN_TOKEN` | All orgs | Setup, provisioning |
| Org Admin | `{org_id}.{random}` | Single org | Org management |
| Team | `{org_id}.{team_id}.{random}` | Single team | Agent execution |

### Auth Flow

```
1. Client sends token in Authorization header
2. Config Service validates token type
3. Returns {auth_kind, org_id, team_node_id}
4. Service checks permissions
```

See: `/config_service/docs/API_REFERENCE.md`

---

## Multi-Tenancy

### Routing

Each team claims routing identifiers:

```json
{
  "routing": {
    "slack_channel_ids": ["C0A4967KRBM"],
    "github_repos": ["incidentfox/mono-repo"],
    "pagerduty_service_ids": ["PXXXXXX"]
  }
}
```

When webhook arrives, Orchestrator extracts identifiers and looks up owning team.

See: `/docs/ROUTING_DESIGN.md`

### Resource Isolation

**Shared Mode** (default):
- All teams use shared agent pods
- Config-based isolation via team tokens
- Cost-effective, simple operations

**Dedicated Mode** (enterprise):
- Team gets isolated agent deployment
- Full K8s pod isolation with custom resources
- Enhanced security and performance guarantees

See: `/docs/MULTI_TENANT_DESIGN.md` for detailed comparison and cost analysis

---

## Agent Systems

### OpenAI Agents SDK (agent/)

**Purpose**: Automated operations

- Multi-agent orchestration (planner → sub-agents)
- 100+ tools (Kubernetes, AWS, Datadog, Slack, GitHub, etc.)
- MCP integration (external tool servers)
- Persistent DB storage
- Retries & error handling

**Use Cases**:
- Auto-remediation (Pager Duty → investigate → propose fix)
- CI/CD bots (GitHub → analyze failure → create PR)
- Scheduled reports (weekly health checks)

### Claude SDK (sre-agent/)

**Purpose**: Interactive investigation

- Isolated K8s sandboxes
- Built-in tools only (Read, Edit, Bash, Grep, Glob)
- Interrupt/resume support
- Persistent filesystem (2 hour TTL)

**Use Cases**:
- Debugging unknown issues
- Exploratory code investigation
- Pair programming

See: `/sre-agent/docs/SDK_COMPARISON.md` for detailed comparison.

---

## Key Design Decisions

### 1. Orchestrator Handles Routing, Agent Handles Execution

**Why**: Separation of concerns
- Orchestrator: Fast webhook acknowledgment (< 3s), routing lookup
- Agent: Slow execution (30-300s), tool invocation, output rendering

### 2. Config Service as Single Source of Truth

**Why**: Multi-tenant configuration management
- Hierarchical inheritance (org → unit → team)
- Centralized token validation
- Audit trail

### 3. Agent Posts Directly to Slack

**Why**: Real-time updates
- Agent can update message as phases complete
- Rich Block Kit UI
- No round-trip through Orchestrator

Alternative (not used): Orchestrator collects results and posts (adds latency).

### 4. Two Agent Systems (OpenAI SDK + Claude SDK)

**Why**: Different use cases
- OpenAI SDK: Automated workflows, multi-agent, integrations
- Claude SDK: Interactive, interrupt support, isolated sandboxes

See: `/docs/ARCHITECTURE_DECISIONS.md` for full ADRs.

---

## External Dependencies

### AWS Services

- **EKS**: Kubernetes cluster (incidentfox-demo)
- **RDS**: PostgreSQL database (Config Service)
- **ECR**: Docker image registry
- **ALB**: Load balancer for ingress
- **API Gateway**: HTTPS proxy for webhooks
- **S3**: RAPTOR KB tree storage

### External APIs

- **Slack**: Bot posts, event subscriptions
- **GitHub**: App webhooks, PR/issue comments
- **PagerDuty**: V3 webhooks
- **Incident.io**: Incident webhooks
- **Coralogix**: Log queries (DataPrime)
- **Snowflake**: Incident enrichment data
- **Datadog**: Metrics & APM
- **Grafana**: Dashboard queries

---

## Scalability

### Current Scale

- 1 org, 1 team (extend-sre)
- ~50 agent runs/day
- 2-5 concurrent webhook requests

### Design Scale

- 100+ orgs
- 1000+ teams
- 10,000+ agent runs/day
- Auto-scaling via HPA

### Bottlenecks

- Config Service in-memory cache (needs Redis)
- Shared agent pod (needs dedicated pods per team)
- Database connection pool

See: `/docs/TECH_DEBT.md` for scaling improvements.

---

## Related Documentation

- [ROUTING_DESIGN.md](ROUTING_DESIGN.md) - Webhook routing design
- [MULTI_TENANT_DESIGN.md](MULTI_TENANT_DESIGN.md) - Multi-tenancy patterns (shared vs dedicated)
- [CONFIG_INHERITANCE.md](CONFIG_INHERITANCE.md) - Config inheritance
- [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) - Key ADRs

# Multi-Tenant Design

**Last Updated**: 2026-01-12
**Status**: Production-ready architecture

---

## Overview

IncidentFox supports multiple organizations and teams with two deployment modes for agent workloads:

1. **Shared Runtime** (default) - Cost-effective, simple operations
2. **Dedicated Pods** (enterprise) - Hard isolation, custom resources

---

## Deployment Modes

### Mode A: Shared Runtime (Default)

All teams share a pool of Agent pods with per-request configuration loading.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agent Service (Shared)                               │
│                         replicas: 2-10 (HPA)                                │
│                                                                              │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐                                    │
│   │ Pod 1   │  │ Pod 2   │  │ Pod N   │   ← K8s load-balances requests     │
│   └─────────┘  └─────────┘  └─────────┘                                    │
│                                                                              │
│   Team A request → Any pod → Load Team A config → Run                       │
│   Team B request → Any pod → Load Team B config → Run                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**How it works**:
1. Orchestrator receives webhook for Team A
2. Orchestrator forwards to shared agent service with Team A token
3. Agent pod loads Team A config from Config Service
4. Agent executes with Team A's tools, prompts, integrations
5. Next request (Team B) uses same pod with different config

**Best for**:
- Most teams (default choice)
- Cost-sensitive deployments
- Simple operations (single deployment to manage)
- Development/staging environments

**Characteristics**:
- ✅ Cost-effective (resource sharing)
- ✅ Simple operations (one deployment)
- ✅ Auto-scaling based on total load
- ✅ Config-based isolation (team tokens)
- ⚠️ Shared CPU/memory resources
- ⚠️ Shared secrets (all integrations in one pod)
- ⚠️ No per-team resource limits

---

### Mode B: Dedicated Pods (Enterprise)

Enterprise teams get their own isolated Agent deployment.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Deployment: agent-dedicated-acme-platform-sre (Team A)                     │
│  Namespace: incidentfox                                                     │
│                                                                              │
│  ┌─────────┐  ┌─────────┐                                                   │
│  │ Pod 1   │  │ Pod 2   │   ← Only handles Team A requests                  │
│  └─────────┘  └─────────┘                                                   │
│                                                                              │
│  Service: agent-dedicated-acme-platform-sre:8080                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  Deployment: agent-shared (All other teams)                                 │
│  Namespace: incidentfox                                                     │
│                                                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                                     │
│  │ Pod 1   │  │ Pod 2   │  │ Pod N   │                                     │
│  └─────────┘  └─────────┘  └─────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**How it works**:
1. Orchestrator receives webhook for Team A (enterprise)
2. Config Service returns `agent_service_url: http://agent-dedicated-acme-platform-sre:8080`
3. Orchestrator forwards to dedicated URL
4. Dedicated pods only serve Team A requests
5. Team B (standard) goes to shared deployment

**Best for**:
- Enterprise customers
- Compliance requirements (data isolation)
- Performance guarantees (SLAs)
- Custom resource limits per team
- Separate secrets management

**Characteristics**:
- ✅ Full CPU/memory isolation
- ✅ Separate secrets per team
- ✅ Custom resource limits
- ✅ Independent scaling
- ✅ Custom node selectors (GPU, high-memory nodes)
- ⚠️ Higher cost (dedicated resources)
- ⚠️ More complex operations (multiple deployments)

---

## Multi-Tenancy Architecture

### Organization Hierarchy

```
Organization: acme
  ├── Org Config: {agents, tools, integrations}
  │
  ├── Unit: platform
  │   ├── Config: inherits org + overrides
  │   └── Team: platform-sre
  │       └── Config: inherits org + unit + overrides
  │
  └── Team: customer-success
      └── Config: inherits org + overrides
```

**Effective Config** = Org config + Unit overrides + Team overrides

See: [CONFIG_INHERITANCE.md](CONFIG_INHERITANCE.md)

---

### Routing Isolation

Each team claims unique routing identifiers:

```json
{
  "team_node_id": "platform-sre",
  "routing": {
    "slack_channel_ids": ["C0A4967KRBM"],
    "github_repos": ["acme/platform"],
    "pagerduty_service_ids": ["PXXXXXX"]
  }
}
```

**Validation**: Each identifier can only belong to ONE team per organization.

**Flow**:
1. Webhook arrives with identifier (slack_channel_id = C0A4967KRBM)
2. Orchestrator calls Config Service routing lookup
3. Returns: org_id = acme, team_node_id = platform-sre, team_token = xxx
4. Orchestrator uses token to fetch team config and forward to agent

See: [ROUTING_DESIGN.md](ROUTING_DESIGN.md)

---

### Token-Based Isolation

| Token Type | Format | Scope | Example |
|------------|--------|-------|---------|
| Global Admin | `env: ADMIN_TOKEN` | All orgs | Setup, provisioning |
| Org Admin | `{org_id}.{random}` | Single org | `acme.xEyGnPw3RCH1l08q2gSb8A` |
| Team | `{org_id}.{team_id}.{random}` | Single team | `acme.platform-sre.J2KnE8rVm...` |

**Agent Execution**:
- Agent receives team token from Orchestrator
- Loads config scoped to that team only
- All tool executions run in team context
- Results posted to team's Slack/GitHub

**Database Scoping**:
- All queries filtered by org_id and team_node_id
- Agent runs logged with org/team context
- Config updates scoped to team's nodes only

---

## Provisioning

### Shared Runtime Provisioning

Simple team creation (default):

```bash
POST /api/v1/admin/provision/team
{
  "org_id": "acme",
  "team_node_id": "platform-sre",
  "routing": {
    "slack_channel_ids": ["C0A4967KRBM"]
  }
}
```

**Actions**:
1. Create team node in Config Service
2. Issue team token
3. Set routing identifiers
4. (Optional) Create AI Pipeline CronJob
5. Team uses shared agent deployment

---

### Dedicated Pods Provisioning

Enterprise team with isolated resources:

```bash
POST /api/v1/admin/provision/team
{
  "org_id": "acme",
  "team_node_id": "enterprise-team",
  "deployment_mode": "dedicated",
  "dedicated_config": {
    "replicas": 2,
    "resources": {
      "cpu": "4",
      "memory": "8Gi"
    },
    "node_selector": {
      "node-type": "high-memory"
    }
  }
}
```

**Actions**:
1. Create team node in Config Service
2. Issue team token
3. Set routing identifiers
4. **Create Kubernetes Deployment** (name: `agent-dedicated-acme-enterprise-team`)
5. **Create Kubernetes Service** (ClusterIP)
6. Store dedicated service URL in team config: `agent_service_url`
7. (Optional) Create AI Pipeline CronJob

**Kubernetes Resources Created**:

```yaml
# Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-dedicated-acme-enterprise-team
  namespace: incidentfox
spec:
  replicas: 2
  selector:
    matchLabels:
      app: agent-dedicated-acme-enterprise-team
  template:
    spec:
      containers:
      - name: agent
        image: 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest
        env:
        - name: TEAM_ID
          value: "enterprise-team"
        - name: ORG_ID
          value: "acme"
        resources:
          limits:
            cpu: "4"
            memory: "8Gi"
          requests:
            cpu: "2"
            memory: "4Gi"
      nodeSelector:
        node-type: high-memory

---
# Service
apiVersion: v1
kind: Service
metadata:
  name: agent-dedicated-acme-enterprise-team
  namespace: incidentfox
spec:
  type: ClusterIP
  selector:
    app: agent-dedicated-acme-enterprise-team
  ports:
  - port: 8080
    targetPort: 8080
```

---

## Request Routing

### Orchestrator Routing Logic

```python
async def route_to_agent(org_id: str, team_node_id: str, request: dict):
    # Get team config from Config Service
    config = await config_service.get_effective_config(
        org_id=org_id,
        team_node_id=team_node_id
    )

    # Check if team has dedicated pods
    if agent_url := config.get("agent_service_url"):
        # Dedicated pod URL stored in config
        # Example: http://agent-dedicated-acme-enterprise-team.incidentfox.svc.cluster.local:8080
        return await call_agent(agent_url, request)
    else:
        # Use shared agent service
        agent_url = "http://incidentfox-agent.incidentfox.svc.cluster.local:8080"
        return await call_agent(agent_url, request)
```

**Routing Decision**:
- If `agent_service_url` exists in config → Route to dedicated pods
- Otherwise → Route to shared service

---

## Comparison Matrix

| Feature | Shared Runtime | Dedicated Pods |
|---------|----------------|----------------|
| **Cost** | ✅ Low (shared resources) | ❌ High (isolated resources) |
| **CPU/Memory Isolation** | ❌ Shared limits | ✅ Per-team limits |
| **Secrets Isolation** | ❌ All teams see all secrets | ✅ Per-team secrets |
| **Scaling** | ✅ HPA based on total load | ✅ HPA per team |
| **Operations** | ✅ Simple (1 deployment) | ⚠️ Complex (N deployments) |
| **Custom Node Selection** | ❌ Not supported | ✅ Custom node selectors |
| **Resource Guarantees** | ❌ No guarantees | ✅ Guaranteed resources |
| **Compliance** | ⚠️ Shared environment | ✅ Full isolation |
| **Performance** | ⚠️ Subject to noisy neighbors | ✅ Predictable performance |
| **Recommended For** | Most teams, dev/staging | Enterprise, compliance needs |

---

## Security Considerations

### Shared Runtime Security

**Isolation Mechanisms**:
1. **Config-based isolation**: Each request loads team-specific config
2. **Token scoping**: Team tokens only access team data
3. **Database row-level filtering**: All queries scoped by org_id + team_node_id
4. **Output isolation**: Results posted to team's Slack/GitHub only

**Shared Resources**:
- CPU/memory pools (K8s resource limits)
- Secrets (all integration credentials in same pod)
- Network namespace (same pod network)

**Risk**: Team A could theoretically access Team B's data if:
- Bug in token validation
- SQL injection bypasses org_id filter
- Secrets leaked via environment variable inspection

---

### Dedicated Pods Security

**Isolation Mechanisms**:
1. **Kubernetes Deployment isolation**: Separate pods per team
2. **Namespace-level RBAC**: (optional) Per-team namespaces
3. **Separate secrets**: Each deployment has own K8s secrets
4. **Network policies**: (optional) Restrict inter-pod traffic
5. **Resource quotas**: Per-deployment limits

**Enhanced Security**:
- No shared memory/CPU
- Separate secrets per deployment
- Physical pod isolation
- Optional namespace isolation (full RBAC separation)

**Risk**: Lower risk - requires K8s-level compromise to cross team boundaries

---

## Cost Analysis

### Shared Runtime Cost

**Assumptions**:
- 10 teams
- 2 shared agent pods (4 CPU, 8Gi RAM each)

**Cost**:
```
2 pods × 4 CPU × $0.031/hour = $0.248/hour = $178/month
2 pods × 8 GiB RAM × $0.0035/hour = $0.056/hour = $40/month

Total: ~$218/month for 10 teams = ~$22/team/month
```

---

### Dedicated Pods Cost

**Assumptions**:
- 10 teams, each with dedicated pods
- Each team: 2 pods (4 CPU, 8Gi RAM per pod)

**Cost**:
```
10 teams × 2 pods × 4 CPU × $0.031/hour = $2.48/hour = $1,786/month
10 teams × 2 pods × 8 GiB RAM × $0.0035/hour = $0.56/hour = $403/month

Total: ~$2,189/month for 10 teams = ~$219/team/month
```

**Cost Ratio**: Dedicated pods are ~10x more expensive than shared runtime

---

## When to Use Each Mode

### Use Shared Runtime When:

✅ Development/staging environments
✅ Small teams (< 20 teams)
✅ Cost is primary concern
✅ No compliance requirements
✅ Moderate traffic (< 1000 agent runs/day)
✅ No custom resource requirements

---

### Use Dedicated Pods When:

✅ Enterprise customers with SLAs
✅ Compliance requirements (SOC2, HIPAA, GDPR)
✅ Need performance guarantees
✅ High traffic teams (> 100 runs/day per team)
✅ Custom resource needs (GPU, high-memory)
✅ Separate secrets management required
✅ Multi-region deployments (isolate per region)

---

## Migration Between Modes

### Migrating from Shared to Dedicated

1. **Provision dedicated pods** (doesn't disrupt shared)
   ```bash
   POST /api/v1/admin/provision/team
   {
     "org_id": "acme",
     "team_node_id": "existing-team",
     "deployment_mode": "dedicated"
   }
   ```

2. **Update team config** with `agent_service_url`
3. **Test dedicated pods** (new webhooks route to dedicated)
4. **Monitor for issues** (24-48 hours)
5. **Keep shared pods as fallback** (can revert by removing `agent_service_url`)

---

### Migrating from Dedicated to Shared

1. **Remove `agent_service_url`** from team config
   ```bash
   PUT /api/v1/admin/orgs/acme/nodes/existing-team/config
   {
     "agent_service_url": null
   }
   ```

2. **Verify webhooks route to shared** (check logs)
3. **Delete K8s resources** after 24 hours
   ```bash
   kubectl delete deployment agent-dedicated-acme-existing-team -n incidentfox
   kubectl delete service agent-dedicated-acme-existing-team -n incidentfox
   ```

---

## Monitoring & Operations

### Key Metrics to Monitor

**Shared Runtime**:
- Agent pod CPU/memory utilization
- Queue depth (if requests wait for pods)
- Per-team request distribution (identify noisy neighbors)
- Error rates by team

**Dedicated Pods**:
- Per-deployment CPU/memory utilization
- Pod replica counts (auto-scaling)
- Per-team latency and error rates
- Cost per team (resource usage)

---

### Troubleshooting

**Issue**: Team using dedicated pods but routing to shared

**Cause**: `agent_service_url` not set in config

**Fix**:
```bash
# Check current config
curl -H "Authorization: Bearer $TEAM_TOKEN" \
  http://config-service:8080/api/v1/config/me/effective

# Should see: "agent_service_url": "http://agent-dedicated-..."
# If missing, update provisioning
```

---

**Issue**: Dedicated pods not scaling

**Cause**: HPA not configured for dedicated deployment

**Fix**:
```bash
kubectl autoscale deployment agent-dedicated-acme-team \
  --cpu-percent=70 --min=2 --max=10 -n incidentfox
```

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [ROUTING_DESIGN.md](ROUTING_DESIGN.md) - Webhook routing details
- [CONFIG_INHERITANCE.md](CONFIG_INHERITANCE.md) - Config inheritance
- [orchestrator/docs/PROVISIONING.md](../orchestrator/docs/PROVISIONING.md) - Provisioning API
- [orchestrator/docs/NORTH_STAR.md](../orchestrator/docs/NORTH_STAR.md) - Target architecture

---

**Last Updated**: 2026-01-12

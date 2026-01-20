# Orchestrator - Team Provisioning

The Orchestrator provides APIs for provisioning teams with optional Kubernetes resources.

---

## Provisioning API

```bash
POST /api/v1/admin/provision/team
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json

{
  "org_id": "extend",
  "team_node_id": "platform-sre",
  "slack_channel_ids": ["C12345"],
  "pipeline_schedule": "0 2 * * *",          # Optional: AI Pipeline CronJob
  "deployment_mode": "dedicated"              # Optional: Dedicated agent pod
}
```

---

## Created Resources

### AI Pipeline CronJob

If `pipeline_schedule` is provided:

```bash
# Created CronJob name pattern
ai-pipeline-{org_id}-{team_node_id}

# Example
kubectl get cronjob ai-pipeline-extend-platform-sre -n incidentfox
```

**Purpose**: Scheduled learning from Slack conversations

### Dedicated Agent Deployment

If `deployment_mode=dedicated`:

```bash
# Created resources:
# 1. Deployment: agent-dedicated-{org_id}-{team_node_id}
# 2. Service: agent-dedicated-{org_id}-{team_node_id}

# Example
kubectl get deployment agent-dedicated-extend-platform-sre -n incidentfox
kubectl get service agent-dedicated-extend-platform-sre -n incidentfox
```

**Purpose**: Isolated agent runtime for enterprise customers

**Service URL** stored in team config:
```json
{
  "agent": {
    "dedicated_service_url": "http://agent-dedicated-extend-platform-sre.incidentfox.svc.cluster.local:8000"
  }
}
```

---

## Deprovisioning API

```bash
POST /api/v1/admin/deprovision/team
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json

{
  "org_id": "extend",
  "team_node_id": "platform-sre",
  "delete_k8s_resources": true
}
```

Deletes:
- CronJob (if exists)
- Dedicated Deployment + Service (if exists)
- Team config in Config Service (optional)

---

## Shared vs Dedicated Runtime

| Mode | Description | When to Use |
|------|-------------|-------------|
| **Shared** (default) | All teams use shared agent pod | Most teams, cost-effective |
| **Dedicated** | Team gets isolated agent pod | Enterprise, compliance requirements |

**Shared Mode**:
- Lower cost (shared resources)
- Faster scaling (pod already running)
- Multi-tenant by design

**Dedicated Mode**:
- Isolated runtime (namespace separation)
- Custom resource limits
- SLA guarantees
- Network isolation

---

## Related Documentation

- `/orchestrator/docs/ARCHITECTURE.md` - Orchestrator design
- `/orchestrator/docs/MULTI_TENANT_DESIGN.md` - Multi-tenant patterns
- `/docs/MULTI_TENANT_DESIGN.md` - System-wide tenancy design

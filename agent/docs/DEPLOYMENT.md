# Agent Service - Deployment Guide

## Build & Push to ECR

```bash
cd agent

# ECR Login
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  103002841599.dkr.ecr.us-west-2.amazonaws.com

# Build for linux/amd64 (EKS runs on x86)
docker build --platform linux/amd64 \
  -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest .

# Push to ECR
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest
```

---

## Deploy to Kubernetes

### Restart Existing Deployment

```bash
kubectl rollout restart deployment/incidentfox-agent -n incidentfox
kubectl rollout status deployment/incidentfox-agent -n incidentfox --timeout=90s
```

### Check Pod Status

```bash
kubectl get pods -n incidentfox -l app=incidentfox-agent
```

### View Logs

```bash
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=50 -f
```

---

## Port Forward for Local Testing

```bash
kubectl port-forward -n incidentfox svc/incidentfox-agent 8080:8080
```

Then test:
```bash
curl http://localhost:8080/health
```

---

## Execute Commands in Pod

```bash
# Run Python in agent pod
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "print('hello')"

# Test tool import
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "
from ai_agent.tools.coralogix_tools import search_coralogix_logs
print('Coralogix tools loaded')
"
```

---

## Environment Variables

Set via Kubernetes deployment:

| Variable | Source | Purpose |
|----------|--------|---------|
| `ANTHROPIC_API_KEY` | Secret | Claude API access |
| `GITHUB_APP_ID` | Secret | GitHub App ID |
| `GITHUB_PRIVATE_KEY_B64` | Secret | GitHub App key |
| `SLACK_BOT_TOKEN` | Secret | Slack API access |
| `CORALOGIX_API_KEY` | Secret | Coralogix access |
| `SNOWFLAKE_ACCOUNT` | Secret | Snowflake connection |
| `CONFIG_SERVICE_URL` | ConfigMap | Config Service endpoint |

See: `infra/k8s/agent-deployment.yaml`

---

## Troubleshooting

### Pod Won't Start

```bash
# Check events
kubectl describe pod -n incidentfox <pod-name>

# Check image pull
kubectl get events -n incidentfox --sort-by='.lastTimestamp'
```

### Import Errors

```bash
# Check installed packages
kubectl exec -n incidentfox deploy/incidentfox-agent -- pip list

# Test specific import
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "import snowflake.connector"
```

### Memory/CPU Issues

```bash
# Check resource usage
kubectl top pod -n incidentfox -l app=incidentfox-agent

# Check resource limits
kubectl get pod -n incidentfox <pod-name> -o json | jq '.spec.containers[0].resources'
```

---

## Health Checks

```bash
# Via kubectl port-forward
curl http://localhost:8080/health

# Via service (from within cluster)
curl http://incidentfox-agent.incidentfox.svc.cluster.local:8080/health

# Via ALB (external)
curl http://k8s-incident-incident-561949e6c7-26896650.us-west-2.elb.amazonaws.com/health
```

---

## Rollback

```bash
# View deployment history
kubectl rollout history deployment/incidentfox-agent -n incidentfox

# Rollback to previous version
kubectl rollout undo deployment/incidentfox-agent -n incidentfox

# Rollback to specific revision
kubectl rollout undo deployment/incidentfox-agent -n incidentfox --to-revision=2
```

---

## Scaling

```bash
# Scale replicas
kubectl scale deployment/incidentfox-agent -n incidentfox --replicas=3

# Check HPA status (if configured)
kubectl get hpa -n incidentfox
```

---

## Testing After Deployment

### 1. Health Check

```bash
curl http://k8s-incident-incident-561949e6c7-26896650.us-west-2.elb.amazonaws.com/health
```

### 2. Test Coralogix Integration

```bash
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "
from ai_agent.tools.coralogix_tools import search_coralogix_logs
import json
result = search_coralogix_logs(query='source logs | limit 3', time_range_minutes=60)
print(json.loads(result)['success'])
"
```

### 3. Test Snowflake Integration

```bash
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "
from ai_agent.tools.snowflake_tools import get_recent_incidents
import json
result = get_recent_incidents(limit=2)
print(json.loads(result)['success'])
"
```

### 4. Test Agent Execution

```bash
# Via Orchestrator webhook (Slack)
# @mention IncidentFox in Slack channel C0A4967KRBM
# Check agent runs in UI: https://ui.incidentfox.ai
```

---

## CI/CD Integration

For automated deployments, use the deployment script:

```bash
./scripts/deploy_agent.sh
```

See: `/docs/DEPLOYMENT.md` for multi-service deployment.

---

## Docker Build Troubleshooting

### OOM on Apple Silicon

If build fails with OOM error:

1. Increase Docker Desktop memory: Settings → Resources → 12+ GB
2. Clean up: `docker system prune -af --volumes`
3. Always use: `docker build --platform linux/amd64`

### Slow Builds

Use BuildKit for faster builds:

```bash
DOCKER_BUILDKIT=1 docker build --platform linux/amd64 \
  -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest .
```

---

## Related Documentation

- `/agent/docs/INTEGRATIONS.md` - Configure external integrations
- `/agent/docs/DYNAMIC_AGENT_SYSTEM.md` - Agent configuration
- `/agent/docs/TOOLS_CATALOG.md` - Available tools
- `/docs/OPERATIONS.md` - Cross-service operations

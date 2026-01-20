# IncidentFox - Troubleshooting Guide

Common issues and solutions.

---

## Pod Won't Start

### Symptoms
- Pod stuck in `Pending`, `CrashLoopBackOff`, or `ImagePullBackOff`

### Diagnosis

```bash
# Check pod status
kubectl get pods -n incidentfox -l app=incidentfox-agent

# Check events
kubectl describe pod -n incidentfox <pod-name>

# Check logs
kubectl logs -n incidentfox <pod-name>
```

### Common Causes

**Image Pull Error**:
```bash
# Verify ECR login (expires after 12 hours)
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  103002841599.dkr.ecr.us-west-2.amazonaws.com

# Verify image exists
aws ecr describe-images --repository-name incidentfox-agent --region us-west-2
```

**Resource Limits**:
```bash
# Check node resources
kubectl top nodes

# Check if pod is evicted
kubectl get events -n incidentfox --sort-by='.lastTimestamp'
```

---

## Webhook Not Routing

### Symptoms
- Slack @mention doesn't trigger investigation
- GitHub webhook doesn't post comment

### Diagnosis

```bash
# Check Orchestrator logs
kubectl logs -n incidentfox deploy/incidentfox-orchestrator --tail=50 -f

# Test routing lookup
kubectl run -n incidentfox test-routing --image=curlimages/curl --rm -it --restart=Never -- \
  curl -s -X POST "http://incidentfox-config-service:8080/api/v1/internal/routing/lookup" \
  -H "X-Internal-Service: orchestrator" \
  -H "Content-Type: application/json" \
  -d '{"identifiers":{"slack_channel_id":"C0A4967KRBM"}}'
```

### Common Causes

**No Team Configured**:
- Team hasn't claimed the routing identifier
- Solution: Update team config with routing identifiers

**Signature Verification Failed**:
```bash
# Check Orchestrator logs for "Invalid signature"
kubectl logs -n incidentfox deploy/incidentfox-orchestrator | grep signature
```
- Solution: Verify webhook secret matches K8s secret

**Orchestrator Can't Reach Config Service**:
```bash
# Test from Orchestrator pod
kubectl exec -n incidentfox deploy/incidentfox-orchestrator -- \
  curl http://incidentfox-config-service:8080/health
```

---

## Integration Not Working

### Coralogix

**Symptoms**: `search_coralogix_logs` returns errors

**Diagnosis**:
```bash
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "
from ai_agent.tools.coralogix_tools import search_coralogix_logs
import json
result = search_coralogix_logs(query='source logs | limit 3', time_range_minutes=60)
print(json.loads(result))
"
```

**Common Causes**:
- Using Send-Your-Data key (`cxtp_*`) instead of Personal Key (`cxup_*`)
- Wrong domain
- API key expired

### Snowflake

**Symptoms**: `get_recent_incidents` returns errors

**Diagnosis**:
```bash
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "
from ai_agent.tools.snowflake_tools import get_recent_incidents
import json
result = get_recent_incidents(limit=2)
print(json.loads(result))
"
```

**Common Causes**:
- Wrong credentials
- Warehouse suspended
- Network connectivity issues

---

## Agent Execution Timeout

### Symptoms
- Agent runs exceed timeout (300s default)
- Partial results returned

### Diagnosis

```bash
# Check agent logs for timeout
kubectl logs -n incidentfox deploy/incidentfox-agent | grep timeout

# Check agent run history in UI
# https://ui.incidentfox.ai/team → Agent Runs
```

### Solutions

**Increase Timeout**:
```python
# In orchestrator/src/incidentfox_orchestrator/agent_client.py
timeout = 600  # 10 minutes
```

**Optimize Agent**:
- Reduce `max_turns` (currently 50)
- Disable verbose tools
- Use more focused prompts

---

## Database Connection Issues

### Symptoms
- Config Service errors: "connection pool exhausted"
- Slow API responses

### Diagnosis

```bash
# Check Config Service logs
kubectl logs -n incidentfox deploy/incidentfox-config-service | grep database

# Check RDS metrics in AWS Console
```

### Solutions

**Restart Config Service**:
```bash
kubectl rollout restart deployment/incidentfox-config-service -n incidentfox
```

**Increase Connection Pool**:
```python
# config_service/src/db/database.py
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=10)
```

---

## Memory/CPU Issues

### Symptoms
- Pod OOMKilled
- Slow performance

### Diagnosis

```bash
# Check resource usage
kubectl top pod -n incidentfox -l app=incidentfox-agent

# Check limits
kubectl get pod -n incidentfox <pod-name> -o json | jq '.spec.containers[0].resources'
```

### Solutions

**Increase Resources**:
Edit `infra/k8s/agent-deployment.yaml`:
```yaml
resources:
  limits:
    memory: "4Gi"  # Increase from 2Gi
    cpu: "4000m"   # Increase from 2000m
```

---

## Web UI Not Loading

### Symptoms
- Blank page
- 500 errors

### Diagnosis

```bash
# Check Web UI logs
kubectl logs -n incidentfox deploy/incidentfox-web-ui --tail=50

# Check if API routes work
curl https://ui.incidentfox.ai/api/team/config
```

### Common Causes

**Config Service Down**:
```bash
kubectl get pods -n incidentfox -l app=incidentfox-config-service
```

**RAPTOR KB Unreachable**:
```bash
# Test RAPTOR API
curl http://internal-raptor-kb-internal-1116386900.us-west-2.elb.amazonaws.com/api/v1/tree/stats
```

---

## Docker Build Failures

### OOM on Apple Silicon

**Symptoms**: `docker build` fails with out-of-memory error

**Solution**:
1. Increase Docker Desktop memory: Settings → Resources → 12+ GB
2. Clean up: `docker system prune -af --volumes`
3. Always use: `docker build --platform linux/amd64`

### Slow Builds

**Solution**: Use BuildKit
```bash
DOCKER_BUILDKIT=1 docker build --platform linux/amd64 ...
```

---

## Slack Not Responding

### Symptoms
- Bot doesn't reply to @mentions
- Buttons don't work

### Diagnosis

```bash
# Check Orchestrator logs for Slack events
kubectl logs -n incidentfox deploy/incidentfox-orchestrator | grep slack

# Verify webhook URL in Slack App settings
# Should be: https://on3vboii0g.execute-api.us-west-2.amazonaws.com/webhooks/slack/events
```

### Common Causes

**Signature Verification Failed**:
- Slack signing secret mismatch
- Check K8s secret: `kubectl get secret incidentfox-slack -n incidentfox -o yaml`

**3-Second Timeout**:
- Orchestrator took > 3s to return 200 OK
- Check Orchestrator logs for slow routing lookup

---

## SQLAlchemy JSONB Not Saving

### Symptoms
- Config changes don't persist
- In-place modifications lost

### Solution

**Use `flag_modified`**:
```python
from sqlalchemy.orm.attributes import flag_modified

config_row.config_json['tools']['enabled'].append('new_tool')
flag_modified(config_row, 'config_json')  # Required!
session.commit()
```

---

## Related Documentation

- `/docs/OPERATIONS.md` - Common operations
- `/docs/DEPLOYMENT.md` - Deployment procedures
- `/sre-agent/docs/KNOWN_ISSUES.md` - SRE Agent limitations

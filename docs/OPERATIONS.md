# IncidentFox Operations Guide

**Version:** 0.1.0 (v0)
**Last Updated:** 2026-01-11
**Target Audience:** SRE, DevOps, Operations Teams

---

## Overview

This guide covers day-to-day operations, monitoring, troubleshooting, and maintenance procedures for IncidentFox deployed on AWS EKS.

**Current Production Environment:**
- **AWS Account:** 103002841599
- **Region:** us-west-2
- **EKS Cluster:** incidentfox-demo
- **Namespace:** incidentfox
- **Services:** 4 (agent, config-service, orchestrator, web-ui)
- **Replicas:** 2 per service (8 pods total)

---

## Quick Reference

### Essential Commands

```bash
# Pod status
kubectl get pods -n incidentfox

# Service health
curl https://orchestrator.incidentfox.ai/health
curl https://ui.incidentfox.ai/health

# View logs (last 100 lines, follow)
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=100 -f

# Restart service
kubectl rollout restart deployment/incidentfox-agent -n incidentfox

# Check rollout status
kubectl rollout status deployment/incidentfox-agent -n incidentfox
```

### Service Endpoints

| Service | Internal | External | Health Check |
|---------|----------|----------|--------------|
| Agent | `incidentfox-agent.incidentfox.svc.cluster.local:8080` | N/A | `/health` |
| Config Service | `incidentfox-config-service.incidentfox.svc.cluster.local:8080` | N/A | `/health` |
| Orchestrator | `incidentfox-orchestrator.incidentfox.svc.cluster.local:8080` | `orchestrator.incidentfox.ai` | `/health` |
| Web UI | `incidentfox-web-ui.incidentfox.svc.cluster.local:3000` | `ui.incidentfox.ai` | `/_next/static` |

---

## 1. Service Health Checks

### Manual Health Checks

```bash
# All pods status
kubectl get pods -n incidentfox

# Expected output: All pods Running, 2/2 READY
NAME                                        READY   STATUS    RESTARTS   AGE
incidentfox-agent-xxx-yyy                  2/2     Running   0          5d
incidentfox-agent-xxx-zzz                  2/2     Running   0          5d
incidentfox-config-service-xxx-yyy         2/2     Running   0          5d
incidentfox-config-service-xxx-zzz         2/2     Running   0          5d
incidentfox-orchestrator-xxx-yyy           2/2     Running   0          5d
incidentfox-orchestrator-xxx-zzz           2/2     Running   0          5d
incidentfox-web-ui-xxx-yyy                 2/2     Running   0          5d
incidentfox-web-ui-xxx-zzz                 2/2     Running   0          5d
```

### Service Endpoints

```bash
# Orchestrator health
curl https://orchestrator.incidentfox.ai/health
# Expected: {"status": "healthy", "timestamp": "..."}

# Config Service health (via port-forward)
kubectl port-forward -n incidentfox svc/incidentfox-config-service 8090:8080 &
curl http://localhost:8090/health

# Web UI (check if Next.js is responding)
curl -I https://ui.incidentfox.ai
# Expected: HTTP/2 200
```

### Database Connectivity

```bash
# Test database connection from config service pod
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  python -c "
from src.db.database import get_db_engine
engine = get_db_engine()
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('DB connection OK:', result.scalar())
"
```

---

## 2. Viewing Logs

### Tail Logs (Real-Time)

```bash
# Agent logs
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=100 -f

# Config Service logs
kubectl logs -n incidentfox deploy/incidentfox-config-service --tail=100 -f

# Orchestrator logs
kubectl logs -n incidentfox deploy/incidentfox-orchestrator --tail=100 -f

# Web UI logs
kubectl logs -n incidentfox deploy/incidentfox-web-ui --tail=100 -f

# All containers in a pod
kubectl logs -n incidentfox incidentfox-agent-xxx-yyy --all-containers=true
```

### Search Logs

```bash
# Search for errors in agent logs (last 1000 lines)
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=1000 | grep -i error

# Search for specific request by correlation_id
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=5000 | grep "correlation_id=abc123"

# Search for webhook failures
kubectl logs -n incidentfox deploy/incidentfox-orchestrator --tail=1000 | grep "signature verification failed"
```

### CloudWatch Logs

```bash
# Tail CloudWatch logs (if configured)
aws logs tail /ecs/incidentfox-agent --follow --region us-west-2
aws logs tail /ecs/incidentfox-config-service --follow --region us-west-2
```

---

## 3. Common Debugging Scenarios

### Scenario 1: Pod Not Starting (ImagePullBackOff)

**Symptoms:**
```bash
kubectl get pods -n incidentfox
NAME                                        READY   STATUS              RESTARTS   AGE
incidentfox-agent-xxx-yyy                  0/2     ImagePullBackOff   0          2m
```

**Cause:** Docker registry authentication failed

**Diagnosis:**
```bash
# Check pod events
kubectl describe pod incidentfox-agent-xxx-yyy -n incidentfox

# Look for error like:
# Failed to pull image "103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest":
# Error response from daemon: pull access denied
```

**Fix:**
```bash
# 1. Verify ECR authentication
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 103002841599.dkr.ecr.us-west-2.amazonaws.com

# 2. Verify image exists
aws ecr describe-images --repository-name incidentfox-agent --region us-west-2

# 3. Recreate imagePullSecret (if needed)
kubectl delete secret regcred -n incidentfox
kubectl create secret docker-registry regcred \
  --docker-server=103002841599.dkr.ecr.us-west-2.amazonaws.com \
  --docker-username=AWS \
  --docker-password=$(aws ecr get-login-password --region us-west-2) \
  -n incidentfox

# 4. Restart deployment
kubectl rollout restart deployment/incidentfox-agent -n incidentfox
```

**Time to Resolve:** 5-10 minutes

---

### Scenario 2: Pod Crashing (CrashLoopBackOff)

**Symptoms:**
```bash
kubectl get pods -n incidentfox
NAME                                        READY   STATUS             RESTARTS   AGE
incidentfox-config-service-xxx-yyy         0/2     CrashLoopBackOff  5          5m
```

**Cause:** Application failing on startup (usually env vars or database connection)

**Diagnosis:**
```bash
# Check logs for error
kubectl logs -n incidentfox incidentfox-config-service-xxx-yyy --previous

# Common errors:
# - "DATABASE_URL not set"
# - "Connection to database failed"
# - "Missing required environment variable"
# - "Module not found" (dependency issue)
```

**Fix - Database Connection:**
```bash
# 1. Verify DATABASE_URL secret exists
kubectl get secret incidentfox-db -n incidentfox

# 2. Check DATABASE_URL value (base64 encoded)
kubectl get secret incidentfox-db -n incidentfox -o jsonpath='{.data.DATABASE_URL}' | base64 -d

# 3. Test database connectivity from pod
kubectl run -it --rm debug --image=postgres:13 --restart=Never -n incidentfox -- \
  psql "postgresql://user:pass@host:5432/dbname"

# 4. If RDS is private, verify security group allows traffic from EKS nodes
```

**Fix - Missing Environment Variable:**
```bash
# 1. Check deployment env vars
kubectl get deployment incidentfox-config-service -n incidentfox -o yaml | grep -A 20 env:

# 2. Add missing env var to deployment
kubectl set env deployment/incidentfox-config-service -n incidentfox NEW_VAR=value

# 3. Or update via Helm values and redeploy
```

**Time to Resolve:** 10-30 minutes

---

### Scenario 3: Service Returning 503 Errors

**Symptoms:**
```bash
curl https://orchestrator.incidentfox.ai/health
# Returns: 503 Service Temporarily Unavailable
```

**Cause:** Readiness probe failing or pods not ready

**Diagnosis:**
```bash
# 1. Check pod status
kubectl get pods -n incidentfox -l app=incidentfox-orchestrator

# 2. Check readiness probe
kubectl describe pod incidentfox-orchestrator-xxx-yyy -n incidentfox | grep -A 5 "Readiness"

# 3. Check service endpoints
kubectl get endpoints incidentfox-orchestrator -n incidentfox

# 4. Check ingress
kubectl get ingress -n incidentfox
kubectl describe ingress incidentfox-orchestrator -n incidentfox
```

**Fix:**
```bash
# 1. If pods are not ready, check logs
kubectl logs -n incidentfox deploy/incidentfox-orchestrator --tail=100

# 2. If health endpoint is failing, test directly
kubectl port-forward -n incidentfox svc/incidentfox-orchestrator 8080:8080 &
curl http://localhost:8080/health

# 3. If ingress misconfigured, verify ALB target group health
aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:us-west-2:103002841599:targetgroup/...

# 4. Restart if needed
kubectl rollout restart deployment/incidentfox-orchestrator -n incidentfox
```

**Time to Resolve:** 5-15 minutes

---

### Scenario 4: Agent Runs Failing

**Symptoms:**
- Agents timing out
- Tools returning errors
- No response to Slack mentions

**Diagnosis:**
```bash
# 1. Check agent logs for errors
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=500 | grep -i error

# 2. Check if OpenAI API key is valid
kubectl exec -n incidentfox deploy/incidentfox-agent -- \
  python -c "import os; import openai; openai.api_key = os.environ['OPENAI_API_KEY']; print(openai.Model.list())"

# 3. Check config service connectivity
kubectl exec -n incidentfox deploy/incidentfox-agent -- \
  curl -v http://incidentfox-config-service.incidentfox.svc.cluster.local:8080/health

# 4. Check agent run history in database
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  psql $DATABASE_URL -c "SELECT id, org_id, status, error FROM agent_runs ORDER BY created_at DESC LIMIT 10;"
```

**Fix:**
```bash
# 1. If OpenAI API key invalid, update secret
kubectl create secret generic incidentfox-secrets \
  --from-literal=OPENAI_API_KEY=sk-new-key \
  --dry-run=client -o yaml | kubectl apply -n incidentfox -f -

# Restart agent to pick up new secret
kubectl rollout restart deployment/incidentfox-agent -n incidentfox

# 2. If config service unreachable, check network policies
kubectl get networkpolicies -n incidentfox

# 3. If database issues, check RDS status
aws rds describe-db-instances --db-instance-identifier incidentfox-db --region us-west-2
```

**Time to Resolve:** 15-30 minutes

---

### Scenario 5: Webhook Not Triggering

**Symptoms:**
- Slack @mention doesn't trigger agent
- GitHub comment doesn't get response
- PagerDuty alert doesn't start investigation

**Diagnosis:**
```bash
# 1. Check orchestrator logs for webhook receipt
kubectl logs -n incidentfox deploy/incidentfox-orchestrator --tail=100 | grep "webhook"

# 2. Test webhook endpoint directly
curl -X POST https://orchestrator.incidentfox.ai/webhooks/slack/events \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# 3. Check signature verification
kubectl logs -n incidentfox deploy/incidentfox-orchestrator --tail=100 | grep "signature"

# 4. Verify webhook secrets
kubectl get secret incidentfox-slack -n incidentfox -o jsonpath='{.data.SLACK_SIGNING_SECRET}' | base64 -d
```

**Fix:**
```bash
# 1. If signature failing, update secret with correct value
kubectl create secret generic incidentfox-slack \
  --from-literal=SLACK_SIGNING_SECRET=correct-secret \
  --dry-run=client -o yaml | kubectl apply -n incidentfox -f -

kubectl rollout restart deployment/incidentfox-orchestrator -n incidentfox

# 2. If webhook URL wrong, update in Slack/GitHub/PagerDuty:
# Slack: https://api.slack.com/apps → Event Subscriptions
# GitHub: Repo Settings → Webhooks
# PagerDuty: Services → Integrations

# 3. Verify ingress routing
kubectl get ingress -n incidentfox -o yaml | grep -A 5 "orchestrator"
```

**Time to Resolve:** 10-20 minutes

---

## 4. Monitoring & Alerting

### Key Metrics to Monitor

| Metric | Source | Threshold | Action |
|--------|--------|-----------|--------|
| Pod restart count | Kubernetes | >5 in 1 hour | Investigate logs, check resources |
| CPU usage | Kubernetes | >80% sustained | Scale up or optimize |
| Memory usage | Kubernetes | >85% | Scale up or investigate leaks |
| Disk usage | Kubernetes | >80% | Clean up or expand |
| Request latency p99 | App metrics | >5 seconds | Investigate slow queries |
| Error rate | App logs | >5% of requests | Check logs, restart if needed |
| Database connections | RDS metrics | >80% of max | Increase max_connections or fix leaks |

### CloudWatch Alarms

```bash
# View existing alarms
aws cloudwatch describe-alarms --region us-west-2 | grep -i incidentfox

# Example alarm: High error rate
aws cloudwatch put-metric-alarm \
  --alarm-name incidentfox-high-error-rate \
  --alarm-description "Alert when error rate > 5%" \
  --metric-name ErrorRate \
  --namespace IncidentFox \
  --statistic Average \
  --period 300 \
  --threshold 5.0 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --region us-west-2
```

### Prometheus Metrics (if configured)

```bash
# Port-forward to metrics endpoint
kubectl port-forward -n incidentfox svc/incidentfox-agent 9090:9090 &

# Query metrics
curl http://localhost:9090/metrics | grep incidentfox

# Key metrics:
# - agent_requests_total
# - agent_duration_seconds
# - tool_calls_total
# - errors_total
```

### Grafana Dashboards

If Grafana is configured:

**Dashboard 1: Service Health**
- Pod status by service
- CPU/Memory usage
- Request rate and latency
- Error rate

**Dashboard 2: Agent Performance**
- Agent runs per hour
- Average run duration
- Tool usage distribution
- Success rate

**Dashboard 3: Database**
- Connection count
- Query latency
- Slow queries
- Disk usage

---

## 5. Routine Maintenance

### Daily Tasks

```bash
# Check pod health
kubectl get pods -n incidentfox

# Review error logs
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=500 --since=24h | grep -i error | wc -l
kubectl logs -n incidentfox deploy/incidentfox-config-service --tail=500 --since=24h | grep -i error | wc -l

# Check disk usage
kubectl exec -n incidentfox deploy/incidentfox-agent -- df -h
```

### Weekly Tasks

```bash
# Review CloudWatch logs for anomalies
aws logs tail /ecs/incidentfox-agent --since 7d --region us-west-2 | grep -i error

# Check database size
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('incidentfox'));"

# Review resource usage trends
kubectl top pods -n incidentfox

# Check for pod restarts
kubectl get pods -n incidentfox -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].restartCount}{"\n"}{end}'

# Review agent runs
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  psql $DATABASE_URL -c "SELECT DATE(created_at), COUNT(*), AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_duration_seconds FROM agent_runs WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY DATE(created_at) ORDER BY DATE(created_at);"
```

### Monthly Tasks

```bash
# Rotate credentials
# - OpenAI API key
# - Slack bot token
# - GitHub tokens
# - Database passwords (coordinate with team)

# Review audit logs
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  psql $DATABASE_URL -c "SELECT action, COUNT(*) FROM node_config_audit WHERE timestamp > NOW() - INTERVAL '30 days' GROUP BY action ORDER BY COUNT(*) DESC;"

# Database vacuum (if not auto-vacuum enabled)
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  psql $DATABASE_URL -c "VACUUM ANALYZE;"

# Check for stale data
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  psql $DATABASE_URL -c "SELECT 'agent_runs' as table_name, COUNT(*) as rows FROM agent_runs WHERE created_at < NOW() - INTERVAL '90 days' UNION SELECT 'agent_sessions', COUNT(*) FROM agent_sessions WHERE created_at < NOW() - INTERVAL '90 days';"

# Review dependencies for updates
cd agent && poetry show --outdated
cd config_service && pip list --outdated
cd web_ui && pnpm outdated
```

### Quarterly Tasks

```bash
# Full infrastructure review
# - Security group rules
# - IAM permissions audit
# - Network policies
# - Resource limits review

# Disaster recovery test
# - Test database backup restore
# - Test service failover
# - Document recovery procedures

# Performance benchmarking
python3 scripts/eval_agent_performance.py --agent-url https://internal-agent-url
```

---

## 6. Deployment Procedures

### Standard Deployment

```bash
# 1. ECR Login
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 103002841599.dkr.ecr.us-west-2.amazonaws.com

# 2. Build (example: agent)
cd agent
docker build --platform linux/amd64 -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest .

# 3. Push
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest

# 4. Restart deployment
kubectl rollout restart deployment/incidentfox-agent -n incidentfox

# 5. Wait for rollout
kubectl rollout status deployment/incidentfox-agent -n incidentfox --timeout=90s

# 6. Verify
kubectl get pods -n incidentfox
curl https://orchestrator.incidentfox.ai/health
```

### Database Migration

```bash
# 1. Backup database first!
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  pg_dump $DATABASE_URL > backup-$(date +%Y%m%d-%H%M%S).sql

# 2. Run migration
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  bash -c "cd /app && alembic upgrade head"

# 3. Verify migration
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  bash -c "cd /app && alembic current"

# 4. Test application
curl https://orchestrator.incidentfox.ai/health
```

### Rollback

```bash
# 1. Rollback deployment
kubectl rollout undo deployment/incidentfox-agent -n incidentfox

# 2. Check rollback status
kubectl rollout status deployment/incidentfox-agent -n incidentfox

# 3. If database migration needs rollback
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  bash -c "cd /app && alembic downgrade -1"

# 4. Verify
kubectl get pods -n incidentfox
```

---

## 7. Incident Response

### Severity Levels

| Severity | Definition | Response Time | Examples |
|----------|------------|---------------|----------|
| **SEV1** | Complete outage | Immediate | All services down, database unreachable |
| **SEV2** | Major degradation | 15 minutes | One service down, high error rate |
| **SEV3** | Minor issue | 1 hour | Single pod crashing, slow response |
| **SEV4** | Maintenance | 4 hours | Planned updates, documentation |

### SEV1 Response

```bash
# 1. Assess impact
kubectl get pods -n incidentfox
kubectl get services -n incidentfox
curl https://orchestrator.incidentfox.ai/health
curl https://ui.incidentfox.ai/health

# 2. Check recent changes
kubectl rollout history deployment/incidentfox-agent -n incidentfox
kubectl rollout history deployment/incidentfox-config-service -n incidentfox

# 3. Gather logs
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=500 > agent-logs.txt
kubectl logs -n incidentfox deploy/incidentfox-config-service --tail=500 > config-logs.txt
kubectl logs -n incidentfox deploy/incidentfox-orchestrator --tail=500 > orch-logs.txt

# 4. Rollback if recent deployment
kubectl rollout undo deployment/incidentfox-agent -n incidentfox

# 5. Notify stakeholders
# - Post in #incidents Slack channel
# - Update status page
# - Email customers if customer-facing

# 6. Document in postmortem template
```

### Communication Template

```
🚨 INCIDENT: [Title]
Severity: SEV[1/2/3]
Status: [Investigating/Identified/Monitoring/Resolved]
Impact: [What is affected]
Started: [Timestamp]

Updates:
[Time] - [Update message]

Root Cause: [Once identified]
Resolution: [What was done]
```

---

## 8. Troubleshooting Tools

### Port Forwarding

```bash
# Config Service
kubectl port-forward -n incidentfox svc/incidentfox-config-service 8090:8080 &

# Agent
kubectl port-forward -n incidentfox svc/incidentfox-agent 8080:8080 &

# Web UI
kubectl port-forward -n incidentfox svc/incidentfox-web-ui 3000:3000 &

# Database (if accessible)
kubectl port-forward -n incidentfox svc/incidentfox-db 5432:5432 &
```

### Debug Container

```bash
# Run debug container in namespace
kubectl run -it --rm debug --image=busybox --restart=Never -n incidentfox -- sh

# Inside debug container:
wget -O- http://incidentfox-config-service:8080/health
nslookup incidentfox-config-service.incidentfox.svc.cluster.local
```

### Database Queries

```bash
# Connect to database
kubectl exec -it -n incidentfox deploy/incidentfox-config-service -- psql $DATABASE_URL

# Useful queries:
SELECT COUNT(*) FROM agent_runs WHERE created_at > NOW() - INTERVAL '1 day';
SELECT status, COUNT(*) FROM agent_runs GROUP BY status;
SELECT org_id, team_node_id, COUNT(*) FROM agent_runs GROUP BY org_id, team_node_id;
```

---

## 9. Performance Tuning

### Horizontal Scaling

```bash
# Scale agent service
kubectl scale deployment incidentfox-agent --replicas=4 -n incidentfox

# Configure HPA (Horizontal Pod Autoscaler)
kubectl autoscale deployment incidentfox-agent \
  --cpu-percent=70 \
  --min=2 \
  --max=10 \
  -n incidentfox

# Check HPA status
kubectl get hpa -n incidentfox
```

### Resource Limits

```yaml
# Update deployment with resource limits
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

Apply via Helm:
```bash
helm upgrade incidentfox ./charts/incidentfox \
  --set agent.resources.limits.memory=2Gi \
  --set agent.resources.limits.cpu=1000m \
  -n incidentfox
```

### Database Tuning

```sql
-- Check slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Analyze table statistics
ANALYZE agent_runs;
ANALYZE node_configs;

-- Vacuum
VACUUM ANALYZE;
```

---

## 10. Backup & Recovery

### Database Backups

```bash
# Manual backup
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  pg_dump $DATABASE_URL | gzip > incidentfox-backup-$(date +%Y%m%d-%H%M%S).sql.gz

# Automated backups (RDS)
aws rds create-db-snapshot \
  --db-instance-identifier incidentfox-db \
  --db-snapshot-identifier incidentfox-snapshot-$(date +%Y%m%d-%H%M%S) \
  --region us-west-2

# List backups
aws rds describe-db-snapshots --db-instance-identifier incidentfox-db --region us-west-2
```

### Restore from Backup

```bash
# 1. Stop services (prevents writes during restore)
kubectl scale deployment --all --replicas=0 -n incidentfox

# 2. Restore database
kubectl run -it --rm restore --image=postgres:13 --restart=Never -n incidentfox -- \
  psql $DATABASE_URL < backup.sql

# 3. Verify data
kubectl exec -n incidentfox deploy/incidentfox-config-service -- \
  psql $DATABASE_URL -c "SELECT COUNT(*) FROM org_nodes;"

# 4. Restart services
kubectl scale deployment --all --replicas=2 -n incidentfox
```

---

## 11. Contact Information

### On-Call Rotation

- **Primary:** See PagerDuty schedule
- **Secondary:** See PagerDuty schedule
- **Escalation:** Engineering Manager

### Support Channels

- **Slack:** #incidentfox-ops (internal)
- **Slack:** #incidentfox-support (customer-facing)
- **Email:** ops@incidentfox.ai
- **PagerDuty:** https://incidentfox.pagerduty.com

### Runbook Updates

This runbook should be updated:
- After each incident (add new scenarios)
- When deployment procedures change
- Monthly review for accuracy

**Last updated:** 2026-01-11
**Next review:** 2026-02-11
**Maintained by:** SRE Team

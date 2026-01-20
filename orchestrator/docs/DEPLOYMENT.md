# Orchestrator Service - Deployment Guide

## Build & Deploy

```bash
cd orchestrator

# ECR Login
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  103002841599.dkr.ecr.us-west-2.amazonaws.com

# Build
docker build --platform linux/amd64 \
  -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-orchestrator:latest .

# Push
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-orchestrator:latest

# Deploy
kubectl rollout restart deployment/incidentfox-orchestrator -n incidentfox
kubectl rollout status deployment/incidentfox-orchestrator -n incidentfox --timeout=90s
```

---

## Health Check

```bash
curl http://orchestrator:8080/health
```

---

## View Logs

```bash
kubectl logs -n incidentfox deploy/incidentfox-orchestrator --tail=50 -f
```

---

## Environment Variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `SLACK_SIGNING_SECRET` | Secret | Verify Slack signatures |
| `GITHUB_WEBHOOK_SECRET` | Secret | Verify GitHub signatures |
| `CONFIG_SERVICE_URL` | ConfigMap | Config Service endpoint |
| `AGENT_SERVICE_URL` | ConfigMap | Agent Service endpoint |

---

## Related Documentation

- `/orchestrator/docs/WEBHOOKS.md` - Webhook handling
- `/orchestrator/docs/PROVISIONING.md` - Team provisioning
- `/docs/DEPLOYMENT.md` - Cross-service deployment

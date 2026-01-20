# IncidentFox - Deployment Guide

Cross-service deployment procedures.

---

## Prerequisites

- AWS CLI configured for account `103002841599`
- kubectl context set to `incidentfox-demo`
- Docker Desktop running

---

## ECR Login

All services require ECR authentication:

```bash
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  103002841599.dkr.ecr.us-west-2.amazonaws.com
```

---

## Deploy All Services

```bash
./scripts/deploy_all.sh
```

This script:
1. Builds all Docker images
2. Pushes to ECR
3. Restarts all deployments
4. Waits for rollout completion

---

## Deploy Individual Service

### Agent

```bash
cd agent
docker build --platform linux/amd64 -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest .
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest
kubectl rollout restart deployment/incidentfox-agent -n incidentfox
kubectl rollout status deployment/incidentfox-agent -n incidentfox --timeout=90s
```

See: `/agent/docs/DEPLOYMENT.md`

### Orchestrator

```bash
cd orchestrator
docker build --platform linux/amd64 -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-orchestrator:latest .
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-orchestrator:latest
kubectl rollout restart deployment/incidentfox-orchestrator -n incidentfox
```

See: `/orchestrator/docs/DEPLOYMENT.md`

### Config Service

```bash
cd config_service
docker build --platform linux/amd64 -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-config-service:latest .
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-config-service:latest
kubectl rollout restart deployment/incidentfox-config-service -n incidentfox
```

See: `/config_service/docs/DEPLOYMENT.md`

### Web UI

```bash
cd web_ui
docker build --platform linux/amd64 -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-web-ui:latest .
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-web-ui:latest
kubectl rollout restart deployment/incidentfox-web-ui -n incidentfox
```

See: `/web_ui/docs/DEPLOYMENT.md`

---

## Database Migrations

Before deploying Config Service:

```bash
cd config_service
alembic upgrade head
```

---

## Verify Deployment

### Check All Pods

```bash
kubectl get pods -n incidentfox
```

All pods should be in `Running` state.

### Check Rollout Status

```bash
kubectl rollout status deployment/incidentfox-agent -n incidentfox
kubectl rollout status deployment/incidentfox-orchestrator -n incidentfox
kubectl rollout status deployment/incidentfox-config-service -n incidentfox
kubectl rollout status deployment/incidentfox-web-ui -n incidentfox
```

### Health Checks

```bash
# Agent
curl http://k8s-incident-incident-561949e6c7-26896650.us-west-2.elb.amazonaws.com/health

# Config Service (via port-forward)
kubectl port-forward -n incidentfox svc/incidentfox-config-service 8090:8080 &
curl http://localhost:8090/health
```

---

## Rollback

### Rollback to Previous Version

```bash
kubectl rollout undo deployment/incidentfox-agent -n incidentfox
```

### Rollback to Specific Revision

```bash
# View history
kubectl rollout history deployment/incidentfox-agent -n incidentfox

# Rollback to revision 3
kubectl rollout undo deployment/incidentfox-agent -n incidentfox --to-revision=3
```

---

## Troubleshooting

### Pod Won't Start

```bash
# Check events
kubectl describe pod -n incidentfox <pod-name>

# Check logs
kubectl logs -n incidentfox <pod-name>
```

### Image Pull Errors

- Verify ECR login is valid (expires after 12 hours)
- Check image exists: `aws ecr describe-images --repository-name incidentfox-agent --region us-west-2`

### OOM on Build

If Docker build fails with OOM:
1. Increase Docker Desktop memory: Settings → Resources → 12+ GB
2. Clean up: `docker system prune -af --volumes`
3. Always use: `--platform linux/amd64`

---

## CI/CD Integration

For automated deployments:
1. GitHub Actions can use same build/push/deploy commands
2. Store AWS credentials as secrets
3. Use `kubectl` with service account token

---

## Related Documentation

- `/docs/OPERATIONS.md` - Operations manual
- `/docs/TROUBLESHOOTING.md` - Common issues
- Service-specific deployment docs in `*/docs/DEPLOYMENT.md`

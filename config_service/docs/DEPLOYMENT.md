# Config Service - Deployment Guide

## Build & Deploy

```bash
cd config_service

# ECR Login
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  103002841599.dkr.ecr.us-west-2.amazonaws.com

# Build
docker build --platform linux/amd64 \
  -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-config-service:latest .

# Push
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-config-service:latest

# Deploy
kubectl rollout restart deployment/incidentfox-config-service -n incidentfox
kubectl rollout status deployment/incidentfox-config-service -n incidentfox --timeout=90s
```

---

## Database Migrations

```bash
cd config_service
alembic upgrade head
```

---

## Seed Organization Config

```bash
python scripts/seed_org_config.py
```

---

## Port Forward

```bash
kubectl port-forward -n incidentfox svc/incidentfox-config-service 8090:8080
```

---

## Environment Variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `DATABASE_URL` | Secret | PostgreSQL connection string |
| `ADMIN_TOKEN` | Secret | Global admin token |

---

## Related Documentation

- `/config_service/docs/DATABASE_SCHEMA.md` - Database schema
- `/config_service/docs/API_REFERENCE.md` - API endpoints

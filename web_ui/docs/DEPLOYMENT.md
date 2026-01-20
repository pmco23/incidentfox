# Web UI - Deployment Guide

## Build & Deploy

```bash
cd web_ui

# ECR Login
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  103002841599.dkr.ecr.us-west-2.amazonaws.com

# Build
docker build --platform linux/amd64 \
  -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-web-ui:latest .

# Push
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-web-ui:latest

# Deploy
kubectl rollout restart deployment/incidentfox-web-ui -n incidentfox
kubectl rollout status deployment/incidentfox-web-ui -n incidentfox --timeout=90s
```

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `CONFIG_SERVICE_URL` | Config Service endpoint |
| `RAPTOR_API_URL` | RAPTOR KB API endpoint |
| `NEXT_PUBLIC_API_URL` | Public API URL (for client-side) |

---

## Access UI

Production: `https://ui.incidentfox.ai`

---

## Development

```bash
npm install
npm run dev  # http://localhost:3000
```

---

## Related Documentation

- `/web_ui/docs/README.md` - Web UI overview
- `/web_ui/docs/BFF_PATTERN.md` - API routes pattern

# Getting Started with IncidentFox

**Quick start guide for new developers.**

---

## Prerequisites

- Docker Desktop
- `kubectl` configured for EKS cluster `incidentfox-demo`
- AWS CLI configured with profile for account `103002841599`
- Python 3.11+, Node.js 18+

---

## Your First Change (30 minutes)

### 1. Clone Repository

```bash
git clone <repo-url>
cd mono-repo
```

### 2. Make a Change

Example: Update agent tool

```bash
cd agent
# Edit src/ai_agent/tools/kubernetes.py
# Make your change...
```

### 3. Build & Deploy

```bash
# ECR Login
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  103002841599.dkr.ecr.us-west-2.amazonaws.com

# Build
docker build --platform linux/amd64 \
  -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest .

# Push
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-agent:latest

# Deploy
kubectl rollout restart deployment/incidentfox-agent -n incidentfox
kubectl rollout status deployment/incidentfox-agent -n incidentfox --timeout=90s
```

### 4. Verify

```bash
# Check pod is running
kubectl get pods -n incidentfox -l app=incidentfox-agent

# View logs
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=20

# Test health check
curl http://k8s-incident-incident-561949e6c7-26896650.us-west-2.elb.amazonaws.com/health
```

---

## Repository Structure

```
mono-repo/
├── agent/                  # OpenAI Agents SDK - automated operations
├── sre-agent/              # Claude SDK - interactive investigations
├── orchestrator/           # Webhook routing & team provisioning
├── config_service/         # Configuration & auth
├── web_ui/                 # Next.js frontend
├── knowledge_base/         # RAPTOR KB
├── ai_pipeline/            # Learning pipeline
├── infra/                  # Kubernetes manifests
└── docs/                   # Documentation
```

---

## Key Services

| Service | Port | Purpose |
|---------|------|---------|
| `incidentfox-agent` | 8080 | AI agents, tool execution |
| `incidentfox-orchestrator` | 8080 | Webhook routing |
| `incidentfox-config-service` | 8080 | Config & auth |
| `incidentfox-web-ui` | 3000 | Frontend |

---

## Common Commands

### View All Services

```bash
kubectl get pods -n incidentfox
```

### View Logs

```bash
kubectl logs -n incidentfox deploy/incidentfox-agent --tail=50 -f
```

### Port Forward

```bash
kubectl port-forward -n incidentfox svc/incidentfox-config-service 8090:8080
```

### Execute in Pod

```bash
kubectl exec -n incidentfox deploy/incidentfox-agent -- python -c "print('hello')"
```

---

## Development Workflow

### Local Development

Most services can run locally:

```bash
# Agent service
cd agent
python -m ai_agent.api_server

# Config service
cd config_service
python -m config_service.main

# Web UI
cd web_ui
npm run dev
```

### Testing Changes

1. Make code change
2. Write tests (if applicable)
3. Build Docker image
4. Deploy to staging/production
5. Verify via logs and health checks

---

## Next Steps

### Week 1: Understand the System

- **Read**: `/docs/ARCHITECTURE.md` - System design
- **Read**: `/docs/ROUTING_DESIGN.md` - Webhook routing
- **Read**: Service-specific READMEs

### Week 2: Make Contributions

- Pick a task from `/docs/TECH_DEBT.md`
- Fix a bug or add a feature
- Deploy and verify

### Month 1: Master the System

- Understand all services
- Know how to debug production issues
- Can deploy confidently

---

## Getting Help

- **Documentation**: Start with service `/docs/README.md` files
- **Runbook**: `/docs/OPERATIONS.md` for common operations
- **Troubleshooting**: `/docs/TROUBLESHOOTING.md` for common issues
- **Tech Debt**: `/docs/TECH_DEBT.md` for known issues

---

## Related Documentation

- `/docs/ARCHITECTURE.md` - System architecture
- `/docs/DEPLOYMENT.md` - Deployment guide
- `/docs/OPERATIONS.md` - Operations manual
- `DEVELOPMENT_KNOWLEDGE.md` - Quick reference

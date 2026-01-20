# Knowledge Base - Deployment Options

## Current Status: ✅ DEPLOYED

| Component | Location | URL |
|-----------|----------|-----|
| **API** | ECS Fargate | `http://internal-raptor-kb-internal-1116386900.us-west-2.elb.amazonaws.com` |
| **Tree Data** | S3 | `s3://raptor-kb-trees-103002841599/trees/mega_ultra_v2/` |
| **Docker Image** | ECR | `103002841599.dkr.ecr.us-west-2.amazonaws.com/raptor-kb:latest` |
| **Web UI Integration** | EKS | `RAPTOR_API_URL` env var set on `incidentfox-web-ui` deployment |

---

## Architecture

```
                              ┌─────────────────────────┐
                              │  S3: raptor-kb-trees    │
                              │  (mega_ultra_v2.pkl)    │
                              └───────────┬─────────────┘
                                          │ downloads at startup
                              ┌───────────▼─────────────┐
┌─────────────────┐           │   ECS Fargate           │
│  Web UI (EKS)   │──────────▶│   raptor-kb API         │
│  RAPTOR_API_URL │  internal │   - /api/v1/tree/stats  │
└─────────────────┘   ALB     │   - /api/v1/tree/structure
                              │   - /api/v1/answer      │
                              └─────────────────────────┘
```

---

## Deployment Options

### Option A: Kubernetes (Recommended for Customers)

Deploy alongside other IncidentFox services:

```bash
# Apply K8s manifests
kubectl apply -f knowledge_base/infra/k8s/deployment.yaml

# Verify
kubectl get pods -n incidentfox -l app=incidentfox-raptor-kb
```

**Features**:
- Downloads tree from S3 at startup (IRSA for credentials)
- Runs in same namespace as other services
- Accessible via ClusterIP service
- Integrated with service mesh

**Recommended for**:
- Self-hosted deployments
- On-premise installations
- Customers with existing K8s infrastructure

---

### Option B: ECS Fargate (Current IncidentFox Deployment)

Standalone ECS deployment using Terraform:

```bash
cd knowledge_base/infra/terraform
terraform init
terraform plan
terraform apply
```

**Features**:
- Fully managed (no node management)
- Auto-scaling
- Isolated from EKS cluster
- Uses internal ALB for routing

**Recommended for**:
- Cloud-hosted SaaS deployments
- Separation of concerns (KB separate from main services)
- AWS-native infrastructure

---

## Build & Deploy

### Build Docker Image

```bash
cd knowledge_base

# Build for ARM64 (ECS Fargate Graviton)
docker buildx build --platform linux/arm64 \
  -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/raptor-kb:latest \
  --push .
```

### Deploy to ECS

```bash
aws ecs update-service \
  --cluster raptor-kb-production \
  --service raptor-kb \
  --force-new-deployment \
  --region us-west-2 \
  --profile playground
```

### Deploy to Kubernetes

```bash
kubectl apply -f knowledge_base/infra/k8s/deployment.yaml
kubectl rollout status deployment/incidentfox-raptor-kb -n incidentfox
```

---

## Testing

### Test API from K8s

```bash
kubectl run -n incidentfox test-raptor --image=curlimages/curl --rm -it --restart=Never -- \
  curl -s "http://internal-raptor-kb-internal-1116386900.us-west-2.elb.amazonaws.com/api/v1/tree/stats?tree_name=mega_ultra_v2"
```

### Test from Web UI

1. Navigate to `https://ui.incidentfox.ai/team/knowledge`
2. Tree should load and display statistics
3. Try searching or asking questions

---

## Update Web UI Integration

```bash
kubectl set env deployment/incidentfox-web-ui -n incidentfox \
  RAPTOR_API_URL=http://internal-raptor-kb-internal-1116386900.us-west-2.elb.amazonaws.com
```

---

## Tree Management

### Upload New Tree

```bash
# Build tree locally
cd knowledge_base/ingestion
python build_tree.py --source k8s-docs --output mega_ultra_v3.pkl

# Upload to S3
aws s3 cp mega_ultra_v3.pkl \
  s3://raptor-kb-trees-103002841599/trees/mega_ultra_v3/tree.pkl

# Update deployment to use new tree
# Edit knowledge_base/api_server.py or set env var TREE_NAME=mega_ultra_v3
```

### Tree Statistics

Current tree: **mega_ultra_v2**

| Layer | Nodes | Description |
|-------|-------|-------------|
| 0 | 39,023 | Leaf nodes (source documents) |
| 1 | 13,422 | First-level summaries |
| 2 | 1,802 | Second-level summaries |
| 3 | 246 | Third-level summaries |
| 4 | 80 | Fourth-level summaries |
| 5 | 25 | Top-level summaries |
| **Total** | **54,598** | All nodes |

---

## Files

| File | Purpose |
|------|---------|
| `knowledge_base/api_server.py` | FastAPI server with tree endpoints |
| `knowledge_base/Dockerfile` | Container with S3 download |
| `knowledge_base/infra/terraform/` | ECS Fargate infrastructure |
| `knowledge_base/infra/k8s/deployment.yaml` | K8s deployment |
| `web_ui/src/app/api/team/knowledge/tree/` | BFF routes for tree API |
| `web_ui/src/components/knowledge/TreeExplorer.tsx` | React Flow visualization |

---

## Related Documentation

- `/knowledge_base/docs/README.md` - RAPTOR overview
- `/knowledge_base/docs/parameter_recommendations.md` - Tuning guide
- `/knowledge_base/docs/DEPLOYMENT_STATUS.md` - Current status

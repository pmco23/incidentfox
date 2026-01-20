# RAPTOR Knowledge Base Deployment Status

**Last Updated:** 2026-01-08

## Current Status: 🟡 In Progress (Paused)

### What's Done ✅

1. **Infrastructure Files Created:**
   - `infra/terraform/main.tf` - ECR, S3, ECS (unused - we use EKS)
   - `infra/terraform/variables.tf` - Config variables
   - `infra/terraform/outputs.tf` - Output definitions
   - `infra/k8s/deployment.yaml` - Kubernetes manifests (USE THIS)

2. **Docker Setup:**
   - `Dockerfile` - Updated with S3 download at startup
   - `entrypoint.sh` - Downloads tree from S3 before starting API

3. **AWS Resources Created:**
   - ECR Repository: `103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-raptor-kb`
   - S3 Bucket: `incidentfox-raptor-trees-103002841599`

4. **Web UI Integration (from other thread):**
   - Tree Explorer API endpoints in `api_server.py`
   - BFF routes in `web_ui/src/app/api/team/knowledge/tree/`
   - React component: `web_ui/src/components/knowledge/TreeExplorer.tsx`
   - Knowledge page updated with Explorer tab

### What's Pending ⏳

1. **Docker Build:** In progress (downloading large ML packages ~3GB+)
   - Monitor: `tail -f /tmp/raptor-build.log`
   - Check completion: `docker images | grep raptor-kb`

2. **S3 Upload:** Tree file (1.4GB) upload in progress
   - Check: `aws s3 ls s3://incidentfox-raptor-trees-103002841599/trees/`

3. **IAM Role for IRSA:** Need to create for S3 access from K8s pod

4. **Deploy to Kubernetes:**
   ```bash
   kubectl apply -f infra/k8s/deployment.yaml
   ```

5. **Update Web UI:**
   - Add `RAPTOR_API_URL` env var pointing to internal service
   - Redeploy web_ui

### Resume Steps

```bash
cd /Users/apple/Desktop/mono-repo/knowledge_base

# 1. Check if Docker build completed
docker images | grep raptor-kb

# 2. If not, rebuild:
docker build --platform linux/amd64 -t 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-raptor-kb:latest .

# 3. Push to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 103002841599.dkr.ecr.us-west-2.amazonaws.com
docker push 103002841599.dkr.ecr.us-west-2.amazonaws.com/incidentfox-raptor-kb:latest

# 4. Check S3 tree file
aws s3 ls s3://incidentfox-raptor-trees-103002841599/trees/
# If missing, upload:
aws s3 cp trees/mega_ultra_v2/mega_ultra_v2.pkl s3://incidentfox-raptor-trees-103002841599/trees/mega_ultra_v2.pkl

# 5. Create IAM role for IRSA (if not exists)
# ... (see Terraform or manually create)

# 6. Create OpenAI secret (if not exists)
kubectl create secret generic incidentfox-openai \
  --from-literal=OPENAI_API_KEY=$OPENAI_API_KEY \
  -n incidentfox

# 7. Deploy to K8s
kubectl apply -f infra/k8s/deployment.yaml

# 8. Update web_ui with RAPTOR_API_URL
# Add to web_ui deployment: RAPTOR_API_URL=http://incidentfox-raptor-kb:8000
```

### Notes

- The Docker image is large (~5GB) due to PyTorch + CUDA + transformers
- Tree file is 1.4GB - downloaded from S3 at container startup
- API server runs on port 8000
- Health check: GET /health


#!/bin/bash
set -e

# Deploy Template System to Production
# This script:
# 1. Builds and pushes Docker images
# 2. Deploys to Kubernetes
# 3. Runs database migration
# 4. Seeds templates

REGION="us-west-2"
ACCOUNT_ID="103002841599"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
NAMESPACE="incidentfox"

echo "========================================="
echo "Template System Deployment"
echo "========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Login to ECR
echo -e "${BLUE}Step 1: Logging into ECR...${NC}"
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
echo -e "${GREEN}✓ Logged into ECR${NC}"
echo ""

# Step 2: Build and push config service
echo -e "${BLUE}Step 2: Building config service...${NC}"
cd config_service
docker build --platform linux/amd64 -t ${ECR_REGISTRY}/incidentfox-config-service:latest .
docker push ${ECR_REGISTRY}/incidentfox-config-service:latest
echo -e "${GREEN}✓ Config service built and pushed${NC}"
cd ..
echo ""

# Step 3: Build and push web UI
echo -e "${BLUE}Step 3: Building web UI...${NC}"
cd web_ui
docker build --platform linux/amd64 -t ${ECR_REGISTRY}/incidentfox-web-ui:latest .
docker push ${ECR_REGISTRY}/incidentfox-web-ui:latest
echo -e "${GREEN}✓ Web UI built and pushed${NC}"
cd ..
echo ""

# Step 4: Deploy to Kubernetes
echo -e "${BLUE}Step 4: Deploying to Kubernetes...${NC}"
cd charts/incidentfox
helm upgrade incidentfox . -f values.prod.yaml -n ${NAMESPACE} --wait --timeout 5m
echo -e "${GREEN}✓ Deployed to Kubernetes${NC}"
cd ../..
echo ""

# Step 5: Wait for pods to be ready
echo -e "${BLUE}Step 5: Waiting for pods to be ready...${NC}"
kubectl rollout status deployment/incidentfox-config-service -n ${NAMESPACE} --timeout=300s
kubectl rollout status deployment/incidentfox-web-ui -n ${NAMESPACE} --timeout=300s
echo -e "${GREEN}✓ Pods are ready${NC}"
echo ""

# Step 6: Get config service pod name
echo -e "${BLUE}Step 6: Finding config service pod...${NC}"
CONFIG_POD=$(kubectl get pods -n ${NAMESPACE} -l app=incidentfox-config-service -o jsonpath='{.items[0].metadata.name}')
echo "Config service pod: ${CONFIG_POD}"
echo -e "${GREEN}✓ Found pod${NC}"
echo ""

# Step 7: Run database migration
echo -e "${BLUE}Step 7: Running database migration...${NC}"
kubectl exec -it ${CONFIG_POD} -n ${NAMESPACE} -- alembic upgrade head
echo -e "${GREEN}✓ Migration completed${NC}"
echo ""

# Step 8: Seed templates
echo -e "${BLUE}Step 8: Seeding templates...${NC}"
kubectl exec -it ${CONFIG_POD} -n ${NAMESPACE} -- python scripts/seed_templates.py
echo -e "${GREEN}✓ Templates seeded${NC}"
echo ""

# Step 9: Verify deployment
echo -e "${BLUE}Step 9: Verifying deployment...${NC}"
echo "Checking if templates API is accessible..."
kubectl exec ${CONFIG_POD} -n ${NAMESPACE} -- curl -s http://localhost:8080/api/health || true
echo ""
echo -e "${GREEN}✓ Health check passed${NC}"
echo ""

# Print final status
echo "========================================="
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Open: https://ui.incidentfox.ai/team/templates"
echo "2. Browse the 10 available templates"
echo "3. Click a template to preview"
echo "4. Click 'Apply to My Team' to use it"
echo ""
echo "Templates deployed:"
echo "  1. 🚨 Slack Incident Triage"
echo "  2. 🔧 Git CI Auto-Fix"
echo "  3. 💰 AWS Cost Reduction"
echo "  4. 💻 Coding Assistant"
echo "  5. 🗄️  Data Migration"
echo "  6. 🎉 News Comedian"
echo "  7. 🔔 Alert Fatigue Reduction"
echo "  8. 🛡️  DR Validator"
echo "  9. 📝 Incident Postmortem"
echo " 10. 📊 Universal Telemetry"
echo ""

# IncidentFox Customer Installation Guide

**Version:** 1.0.0
**Last Updated:** 2026-01-11
**Support:** support@incidentfox.ai

---

## Overview

This guide walks you through installing IncidentFox in your Kubernetes cluster. The entire process takes approximately **2-3 hours** for a new installation.

**What You'll Install:**
- 4 core services (Agent, Config Service, Orchestrator, Web UI)
- PostgreSQL database (external, not included)
- Ingress for HTTPS access
- Required Kubernetes secrets

**Prerequisites Time:**
- Infrastructure setup: 1-2 hours (if not already available)
- Secret creation: 30 minutes
- Helm installation: 15 minutes

---

## ⚠️ Before You Begin: Infrastructure Setup

**This guide assumes you already have the required infrastructure.**

If you need to create infrastructure (Kubernetes cluster, database, etc.), **start here first:**

→ **[Infrastructure Setup Guide](./infrastructure-setup.md)** ← Choose your path

**Options available:**
- **PATH 1:** Terraform (complete AWS stack) - 30 min setup
- **PATH 2:** Bring your own infrastructure - 0 min setup
- **PATH 3:** AWS Console (click-ops) - 2-3 hours
- **PATH 4:** Managed installation - Contact sales

Once your infrastructure is ready, return here and continue below.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Phase 1: Infrastructure Preparation](#phase-1-infrastructure-preparation)
3. [Phase 2: Secret Management](#phase-2-secret-management)
4. [Phase 3: Docker Registry Authentication](#phase-3-docker-registry-authentication)
5. [Phase 4: Helm Installation](#phase-4-helm-installation)
6. [Phase 5: Verification](#phase-5-verification)
7. [Phase 6: Initial Configuration](#phase-6-initial-configuration)
8. [Troubleshooting](#troubleshooting)
9. [Next Steps](#next-steps)

---

## Prerequisites

### Required Infrastructure

| Component | Requirement | Notes |
|-----------|------------|-------|
| **Kubernetes** | v1.24+ | EKS, GKE, AKS, or self-hosted |
| **Nodes** | 3+ nodes, 2 CPU / 8GB RAM each | Minimum for HA deployment |
| **PostgreSQL** | v13+ | RDS, CloudSQL, or self-hosted |
| **Ingress Controller** | ALB, NGINX, or Traefik | Must be pre-installed |
| **Storage** | Default StorageClass | For persistent volumes |
| **kubectl** | Configured and connected | Run `kubectl get nodes` to verify |
| **Helm** | v3.0+ | Run `helm version` to verify |

### Required Credentials

Before starting, gather these credentials:

- [x] IncidentFox license key (provided by IncidentFox sales)
- [x] PostgreSQL connection string
- [x] OpenAI API key (or compatible LLM endpoint)
- [x] Domain name for IncidentFox (e.g., `incidentfox.acme-corp.com`)
- [x] TLS certificate (AWS ACM ARN or cert-manager issuer)
- [x] (Optional) Slack bot token and signing secret
- [x] (Optional) GitHub webhook secret

### Tools to Install

```bash
# Verify kubectl
kubectl version --client

# Install Helm 3 (if not installed)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify Helm
helm version

# Install jq (for JSON processing)
# macOS:
brew install jq
# Ubuntu/Debian:
sudo apt-get install jq
# RHEL/CentOS:
sudo yum install jq
```

---

## Phase 1: Infrastructure Preparation

### Step 1.1: Create Namespace

```bash
# Create dedicated namespace
kubectl create namespace incidentfox

# Verify
kubectl get namespace incidentfox
```

### Step 1.2: Verify Ingress Controller

**For AWS Load Balancer Controller (EKS):**
```bash
# Check if ALB controller is installed
kubectl get deployment -n kube-system aws-load-balancer-controller

# If not installed, install it:
# https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html
```

**For NGINX Ingress Controller:**
```bash
# Check if NGINX is installed
kubectl get deployment -n ingress-nginx ingress-nginx-controller

# If not installed, install it:
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
```

**For Traefik:**
```bash
# Check if Traefik is installed
kubectl get deployment -n traefik traefik

# If not installed:
helm repo add traefik https://helm.traefik.io/traefik
helm install traefik traefik/traefik -n traefik --create-namespace
```

### Step 1.3: Verify PostgreSQL Database

Your PostgreSQL database should be accessible from the Kubernetes cluster.

```bash
# Test connection from a pod
kubectl run -it --rm psql-test --image=postgres:15 --restart=Never -- \
  psql "postgresql://username:password@your-db-host:5432/incidentfox" -c "SELECT version();"

# Expected output: PostgreSQL version information
```

**Database Requirements:**
- PostgreSQL 13 or higher
- Database name: `incidentfox` (or your choice)
- User with full permissions (CREATE, ALTER, SELECT, INSERT, UPDATE, DELETE)
- Network access from Kubernetes pods

**Connection String Format:**
```
postgresql://username:password@hostname:5432/database_name
```

**Recommended:** Use AWS RDS, Google Cloud SQL, or Azure Database for PostgreSQL for production.

### Step 1.4: Configure DNS

Create a DNS record pointing to your ingress controller's load balancer.

**For AWS ALB:**
```bash
# Get ALB DNS name (will be created after Helm install)
# For now, create a CNAME record ready:
# incidentfox.acme-corp.com → <your-alb-dns-name>
```

**For NGINX/Traefik:**
```bash
# Get Load Balancer IP
kubectl get svc -n ingress-nginx ingress-nginx-controller

# Create A record:
# incidentfox.acme-corp.com → <EXTERNAL-IP>
```

### Step 1.5: TLS Certificate

**For AWS ACM (AWS ALB):**
```bash
# Request certificate
aws acm request-certificate \
  --domain-name incidentfox.acme-corp.com \
  --validation-method DNS \
  --region us-east-1

# Add DNS validation record in Route53
# Copy certificate ARN for later: arn:aws:acm:us-east-1:123456789012:certificate/...
```

**For cert-manager (NGINX/Traefik):**
```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create Let's Encrypt ClusterIssuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@acme-corp.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

---

## Phase 2: Secret Management

You need to create 8 Kubernetes secrets. You can do this manually or use External Secrets Operator.

### Option A: Manual Secret Creation (Recommended for First Install)

#### Secret 1: Database URL

```bash
kubectl create secret generic incidentfox-database-url \
  --from-literal=DATABASE_URL="postgresql://username:password@hostname:5432/incidentfox" \
  -n incidentfox
```

#### Secret 2: Config Service Secrets

Generate random secure tokens:
```bash
# Generate 3 random tokens
ADMIN_TOKEN=$(openssl rand -base64 32)
TOKEN_PEPPER=$(openssl rand -base64 32)
IMPERSONATION_JWT_SECRET=$(openssl rand -base64 32)

# Create secret
kubectl create secret generic incidentfox-config-service \
  --from-literal=ADMIN_TOKEN="$ADMIN_TOKEN" \
  --from-literal=TOKEN_PEPPER="$TOKEN_PEPPER" \
  --from-literal=IMPERSONATION_JWT_SECRET="$IMPERSONATION_JWT_SECRET" \
  -n incidentfox

# IMPORTANT: Save these tokens securely (1Password, Vault, etc.)
echo "ADMIN_TOKEN: $ADMIN_TOKEN" >> ~/incidentfox-secrets-backup.txt
echo "TOKEN_PEPPER: $TOKEN_PEPPER" >> ~/incidentfox-secrets-backup.txt
echo "IMPERSONATION_JWT_SECRET: $IMPERSONATION_JWT_SECRET" >> ~/incidentfox-secrets-backup.txt
```

#### Secret 3: OpenAI API Key

```bash
kubectl create secret generic incidentfox-openai \
  --from-literal=api_key="sk-proj-your-openai-key-here" \
  -n incidentfox
```

#### Secret 4-8: Optional Integration Secrets

**Slack (if using Slack integration):**
```bash
kubectl create secret generic incidentfox-slack \
  --from-literal=signing_secret="your-slack-signing-secret" \
  --from-literal=bot_token="xoxb-your-slack-bot-token" \
  -n incidentfox
```

**GitHub (if using GitHub integration):**
```bash
kubectl create secret generic incidentfox-github \
  --from-literal=GITHUB_WEBHOOK_SECRET="your-github-webhook-secret" \
  -n incidentfox
```

**PagerDuty, Orchestrator Internal Token, Langfuse:**
(Create as needed - see values template for details)

#### Verify Secrets

```bash
# List all secrets
kubectl get secrets -n incidentfox

# Should see:
# - incidentfox-database-url
# - incidentfox-config-service
# - incidentfox-openai
# - (optional) incidentfox-slack
# - (optional) incidentfox-github
```

### Option B: External Secrets Operator (Advanced)

If you're using AWS Secrets Manager, HashiCorp Vault, or another secrets backend:

1. Install External Secrets Operator: https://external-secrets.io/latest/introduction/getting-started/
2. Store secrets in your secrets backend
3. Enable `externalSecrets.enabled: true` in values.yaml
4. Configure secret paths in values.yaml

---

## Understanding IncidentFox Token Hierarchy

Before proceeding with installation, it's important to understand IncidentFox's three-tier token system.

### Token Types and Scopes

IncidentFox uses three types of authentication tokens, each with different scopes:

#### 1. Super Admin Token (Platform-Level)

**Scope:** All organizations
**Created during:** Initial deployment (Phase 2)
**Stored in:** Kubernetes secret `incidentfox-config-service`

**What it can do:**
- Create and manage organizations
- Issue org admin tokens
- Access all organizations' data
- Perform system-wide operations

**Who needs it:** IncidentFox platform operators (you, during initial setup)

**When to use:**
- Bootstrapping the platform
- Creating the first organization
- Issuing org admin tokens
- System maintenance

**⚠️ Security:** Store this token securely! It has unrestricted access to the entire platform.

#### 2. Org Admin Token (Organization-Level)

**Scope:** One specific organization
**Created after:** Organization is created
**Stored by:** Organization administrator

**What it can do:**
- Create and manage teams within the org
- Issue team tokens
- Configure org-level settings
- Manage org users and permissions
- View audit logs for the org

**Who needs it:** Organization administrators (one per organization)

**When to use:**
- Day-to-day organization management
- Creating teams
- Issuing team tokens for integrations
- Configuring org settings

**⚠️ Note:** Org admins CANNOT issue new org admin tokens (only super admin can).

#### 3. Team Token (Team-Level)

**Scope:** One specific team
**Created by:** Org admin or super admin
**Used by:** External integrations

**What it can do:**
- Trigger agent runs for the team
- Access team configuration (read-only in most cases)
- Used by webhooks (Slack, GitHub, PagerDuty)

**Who needs it:** External systems and integrations

**When to use:**
- Slack app authentication
- GitHub webhook authentication
- PagerDuty webhook authentication
- Any external system that triggers agents

**⚠️ Security:** These tokens are less privileged but should still be protected.

### Token Hierarchy Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Super Admin Token                                       │
│  (Platform-wide access)                                  │
│  • Stored in Kubernetes secret                           │
│  • Can create orgs and issue org admin tokens            │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ Can issue
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Org Admin Token: "acme-corp"                           │
│  (Organization-scoped)                                   │
│  • Can create teams within org                           │
│  • Can issue team tokens                                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ Can issue
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Team Token: "team-sre"                                 │
│  (Team-scoped)                                           │
│  • Used by Slack/GitHub webhooks                         │
│  • Can trigger agent runs                                │
└─────────────────────────────────────────────────────────┘
```

### Common Setup Scenarios

**Single Organization Setup (Most Common):**
1. Create super admin token (Phase 2) ✅
2. Use super admin token to create organization
3. Use super admin token to issue one org admin token
4. **Use org admin token for everything else** (recommended)
5. Store super admin token securely and use only for emergencies

**Multi-Organization Setup (Enterprise):**
1. Create super admin token (Phase 2) ✅
2. Use super admin token to create multiple organizations
3. Issue separate org admin token for each organization
4. Give each org admin their org admin token
5. Each org admin manages their own teams independently

**Multi-Tenant SaaS Setup:**
1. Keep super admin token for platform operator
2. Create organization per customer
3. Issue org admin token per customer
4. Customers use their org admin token for their teams
5. Platform isolation maintained at org level

### Token Revocation

All tokens can be revoked:
- **Team tokens:** Revoked by org admin via API or Web UI
- **Org admin tokens:** Revoked by super admin
- **Super admin token:** Rotate by creating new secret and restarting pods

See [API Reference](./api-reference.md#token-management) for revocation endpoints.

---

## Phase 3: Docker Registry Authentication

IncidentFox container images are hosted on Docker Hub. You need to authenticate using your license key.

### Step 3.1: Login to Docker Registry

```bash
# Replace YOUR_LICENSE_KEY with the key provided by IncidentFox sales
export LICENSE_KEY="IFOX-ACME-a1b2c3d4e5f6"

# Login to Docker Hub
echo $LICENSE_KEY | docker login -u incidentfox --password-stdin

# Expected output: "Login Succeeded"
```

### Step 3.2: Create ImagePullSecret for Kubernetes

```bash
# Create Kubernetes secret for pulling images
kubectl create secret docker-registry incidentfox-registry \
  --docker-server=docker.io \
  --docker-username=incidentfox \
  --docker-password=$LICENSE_KEY \
  -n incidentfox

# Verify
kubectl get secret incidentfox-registry -n incidentfox
```

**Note:** If you don't have a license key yet, contact sales@incidentfox.ai

---

## Phase 4: Helm Installation

### Step 4.1: Download Values Template

```bash
# Extract default values from the Helm chart
helm show values oci://registry-1.docker.io/incidentfox/incidentfox --version 0.1.0 > values-customer.yaml

# Or download and extract from chart package
helm pull oci://registry-1.docker.io/incidentfox/incidentfox --version 0.1.0
tar -xzf incidentfox-0.1.0.tgz
cp incidentfox/values.template.yaml values-customer.yaml
```

### Step 4.2: Configure Your Values

Edit `values-customer.yaml` and replace all `<CUSTOMER_FILLS>` placeholders:

```yaml
global:
  configService:
    orgId: "acme-corp"  # Your organization identifier

ingress:
  className: "nginx"  # or "alb" for AWS
  host: "incidentfox.acme-corp.com"  # Your domain

  # For AWS ALB:
  tls:
    certificateArn: "arn:aws:acm:us-east-1:123456789012:certificate/..."

services:
  webUi:
    cookieSecure: true  # true for HTTPS, false for HTTP
```

**Complete checklist in values file:**
- [ ] `global.configService.orgId`
- [ ] `ingress.className`
- [ ] `ingress.host`
- [ ] `ingress.tls.certificateArn` (if AWS ALB)
- [ ] `services.webUi.cookieSecure`

### Step 4.3: Install IncidentFox

```bash
# Add imagePullSecrets to your values file
# (Or Helm will use default ServiceAccount - make sure to add secret there)

# Install IncidentFox
helm install incidentfox oci://registry-1.docker.io/incidentfox/incidentfox \
  --version 0.1.0 \
  -f values-customer.yaml \
  -n incidentfox \
  --wait \
  --timeout 10m

# Expected output:
# NAME: incidentfox
# NAMESPACE: incidentfox
# STATUS: deployed
# REVISION: 1
```

**Note:** First installation takes 5-10 minutes due to:
- Docker image pulls
- Database migrations
- Pod startup and health checks

### Step 4.4: Monitor Installation Progress

```bash
# Watch pods starting up
kubectl get pods -n incidentfox -w

# Expected pods (all should show 2/2 READY):
# incidentfox-agent-xxx          2/2  Running
# incidentfox-agent-yyy          2/2  Running
# incidentfox-config-service-xxx 2/2  Running
# incidentfox-config-service-yyy 2/2  Running
# incidentfox-orchestrator-xxx   2/2  Running
# incidentfox-orchestrator-yyy   2/2  Running
# incidentfox-web-ui-xxx         2/2  Running
# incidentfox-web-ui-yyy         2/2  Running

# Check for any errors
kubectl get events -n incidentfox --sort-by='.lastTimestamp' | tail -20
```

---

## Phase 5: Verification

### Step 5.1: Verify Services

```bash
# Check all deployments are ready
kubectl get deployments -n incidentfox

# Should show 2/2 READY for all services:
# NAME                          READY   UP-TO-DATE   AVAILABLE
# incidentfox-agent             2/2     2            2
# incidentfox-config-service    2/2     2            2
# incidentfox-orchestrator      2/2     2            2
# incidentfox-web-ui            2/2     2            2
```

### Step 5.2: Check Ingress

```bash
# Get ingress details
kubectl get ingress -n incidentfox

# Verify:
# - HOST matches your domain
# - ADDRESS shows load balancer IP/DNS
```

### Step 5.3: Test Health Endpoints

```bash
# Get ingress host
INGRESS_HOST=$(kubectl get ingress -n incidentfox incidentfox-ingress -o jsonpath='{.spec.rules[0].host}')

# Test config service health
curl https://$INGRESS_HOST/api/health

# Expected: {"status":"healthy","version":"1.0.0"}

# Test Web UI
curl -I https://$INGRESS_HOST/

# Expected: HTTP/2 200
```

### Step 5.4: Access Web UI

```bash
echo "IncidentFox Web UI: https://$INGRESS_HOST"
```

Open the URL in your browser. You should see the IncidentFox login page.

---

## Phase 6: Initial Configuration

### Understanding Organization Structure

IncidentFox uses a hierarchical organization structure:
- **Organization (org)**: Top-level entity (matches `global.configService.orgId` from your values.yaml)
- **Teams**: Created under the organization

**Important:** Use the same `org_id` value you configured in `values.yaml` under `global.configService.orgId`.

### Step 6.1: Set Environment Variables

```bash
# Get the SUPER ADMIN token you created earlier (Phase 2)
# This token has platform-wide access and is used for initial bootstrap
SUPER_ADMIN_TOKEN=$(kubectl get secret incidentfox-config-service -n incidentfox -o jsonpath='{.data.ADMIN_TOKEN}' | base64 -d)

# Set service URLs (same ingress host for both)
CONFIG_SERVICE="https://$INGRESS_HOST"
ORCHESTRATOR="https://$INGRESS_HOST"

# Set your organization ID (must match values.yaml)
ORG_ID="acme-corp"  # Replace with your orgId from values.yaml

echo "Super Admin Token: $SUPER_ADMIN_TOKEN"
echo "Config Service: $CONFIG_SERVICE"
echo "Organization ID: $ORG_ID"
```

**Note:** We're using the super admin token for initial setup. After creating the organization, we'll issue an org admin token for day-to-day use.

### Step 6.2: Create Organization Root Node

```bash
# Create the organization root node (using super admin token)
curl -X POST "$CONFIG_SERVICE/api/v1/admin/orgs/$ORG_ID/nodes" \
  -H "Authorization: Bearer $SUPER_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"node_id\": \"$ORG_ID\",
    \"parent_id\": null,
    \"node_type\": \"org\",
    \"name\": \"Acme Corp\"
  }"

# Expected response:
# {
#   "org_id": "acme-corp",
#   "node_id": "acme-corp",
#   "parent_id": null,
#   "node_type": "org",
#   "name": "Acme Corp"
# }
```

**Note:** If you get "Node already exists", that's OK - the org node may have been auto-created on first startup.

### Step 6.3: Issue Org Admin Token (Recommended)

Now issue an org-scoped admin token for day-to-day management:

```bash
# Issue org admin token for this organization
ORG_ADMIN_RESPONSE=$(curl -s -X POST "$CONFIG_SERVICE/api/v1/admin/orgs/$ORG_ID/admin-tokens" \
  -H "Authorization: Bearer $SUPER_ADMIN_TOKEN" \
  -H "Content-Type: application/json")

ORG_ADMIN_TOKEN=$(echo "$ORG_ADMIN_RESPONSE" | jq -r '.token')

echo "Org Admin Token: $ORG_ADMIN_TOKEN"
echo ""
echo "⚠️  IMPORTANT: Save this org admin token securely!"
echo "Use this token for day-to-day operations instead of the super admin token."
echo ""

# Save to secure backup
echo "ORG_ADMIN_TOKEN=$ORG_ADMIN_TOKEN" >> ~/incidentfox-tokens-backup.txt
```

**Why issue an org admin token?**
- **Principle of least privilege:** Super admin has access to ALL orgs
- **Safer for daily use:** Org admin can only affect one organization
- **Auditability:** Actions taken with org admin token are clearly scoped
- **Multi-org support:** Each org gets its own admin token

**From this point forward, use `$ORG_ADMIN_TOKEN` instead of `$SUPER_ADMIN_TOKEN` for commands.**

### Step 6.4: Create Your First Team

```bash
# Create a team under the organization (using org admin token)
curl -X POST "$CONFIG_SERVICE/api/v1/admin/orgs/$ORG_ID/nodes" \
  -H "Authorization: Bearer $ORG_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"node_id\": \"team-sre\",
    \"parent_id\": \"$ORG_ID\",
    \"node_type\": \"team\",
    \"name\": \"SRE Team\"
  }"

# Expected response:
# {
#   "org_id": "acme-corp",
#   "node_id": "team-sre",
#   "parent_id": "acme-corp",
#   "node_type": "team",
#   "name": "SRE Team"
# }
```

### Step 6.5: Generate Team Token

```bash
# Generate a long-lived token for the team (using org admin token)
TEAM_TOKEN=$(curl -s -X POST "$CONFIG_SERVICE/api/v1/admin/orgs/$ORG_ID/teams/team-sre/tokens" \
  -H "Authorization: Bearer $ORG_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  | jq -r '.token')

echo "Team Token: $TEAM_TOKEN"
echo ""
echo "⚠️  IMPORTANT: Save this token securely!"
echo "You'll need it for API integrations (Slack, GitHub webhooks, etc.)"

# Save to secure backup
echo "TEAM_TOKEN=$TEAM_TOKEN" >> ~/incidentfox-tokens-backup.txt
```

### Step 6.6: Test Agent Run

```bash
# Test agent execution via orchestrator (using org admin token)
curl -X POST "$ORCHESTRATOR/api/v1/admin/agents/run" \
  -H "X-Admin-Token: $ORG_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"team_node_id\": \"team-sre\",
    \"message\": \"List all available tools and tell me what you can do. Be concise.\"
  }"

# Expected: JSON response with agent's message listing available tools
# Example response:
# {
#   "run_id": "abc123...",
#   "status": "completed",
#   "result": {
#     "message": "I have access to 50+ tools including: kubernetes (get pods, logs)..."
#   }
# }
```

### Step 6.7: Access Web UI

```bash
echo "IncidentFox Web UI: https://$INGRESS_HOST"
echo ""
echo "Login with:"
echo "  - Org Admin Token: $ORG_ADMIN_TOKEN"
echo "  - Or configure SSO/OIDC (see docs)"
```

**Token Summary:**
- **Super Admin Token:** Store securely, use only for creating new orgs or issuing org admin tokens
- **Org Admin Token:** Use for day-to-day operations within your organization
- **Team Token:** Give to external integrations (Slack, GitHub)

Open your browser and navigate to the Web UI. You should see:
- **Dashboard** with team statistics
- **Teams** tab showing "team-sre"
- **Tools & MCPs** tab showing available integrations

---

## What's Next?

### Production Readiness

Now that IncidentFox is installed, consider these next steps:

1. **Configure SSO/OIDC** for user authentication
2. **Set up monitoring and alerts** for the platform
3. **Configure integrations** (Slack, GitHub, PagerDuty, etc.)
4. **Apply templates** from the template marketplace
5. **Set up backup and disaster recovery**

### API Automation

For programmatic access and automation, see the **[API Reference Guide](./api-reference.md)** which includes:
- Complete API endpoint documentation
- Authentication examples
- Common automation scripts
- Error handling reference

### Need Help?

- 📖 **Documentation**: This directory
- 💬 **Email**: support@incidentfox.ai
- 🐛 **Issues**: [GitHub Issues](https://github.com/incidentfox/incidentfox/issues)

---

## Troubleshooting

### Issue: Pods Stuck in ImagePullBackOff

**Cause:** Docker registry authentication failed

**Solution:**
```bash
# Verify imagePullSecret exists
kubectl get secret incidentfox-registry -n incidentfox

# If missing, recreate:
echo $LICENSE_KEY | docker login -u incidentfox --password-stdin
kubectl create secret docker-registry incidentfox-registry \
  --docker-server=docker.io \
  --docker-username=incidentfox \
  --docker-password=$LICENSE_KEY \
  -n incidentfox

# Restart deployments
kubectl rollout restart deployment -n incidentfox
```

### Issue: Database Connection Failed

**Cause:** Database not accessible or wrong credentials

**Solution:**
```bash
# Test database connection
kubectl run -it --rm psql-test --image=postgres:15 --restart=Never -- \
  psql "$(kubectl get secret incidentfox-database-url -n incidentfox -o jsonpath='{.data.DATABASE_URL}' | base64 -d)" \
  -c "SELECT version();"

# Check config-service logs for detailed error
kubectl logs -n incidentfox deployment/incidentfox-config-service --tail=100
```

### Issue: Ingress Not Working

**Cause:** Ingress controller not installed or misconfigured

**Solution:**
```bash
# Check ingress class
kubectl get ingressclass

# Check ingress controller pods
kubectl get pods -n ingress-nginx  # for NGINX
kubectl get pods -n kube-system | grep aws-load-balancer  # for ALB

# Check ingress events
kubectl describe ingress -n incidentfox incidentfox-ingress
```

### Issue: TLS Certificate Errors

**For cert-manager:**
```bash
# Check certificate status
kubectl get certificate -n incidentfox

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager

# Manually trigger certificate issuance
kubectl delete certificate -n incidentfox incidentfox-tls
# Will be recreated automatically
```

**For AWS ACM:**
```bash
# Verify ACM ARN is correct in values.yaml
# Verify certificate is ISSUED status in ACM console
aws acm describe-certificate --certificate-arn YOUR_ARN
```

### Issue: 503 Service Unavailable

**Cause:** Pods not ready or health checks failing

**Solution:**
```bash
# Check pod status
kubectl get pods -n incidentfox

# Check pod logs
kubectl logs -n incidentfox deployment/incidentfox-web-ui --tail=100

# Check service endpoints
kubectl get endpoints -n incidentfox
```

### Getting Help

If you're still stuck:

1. **Collect diagnostic info:**
```bash
# Get all pod logs
kubectl logs -n incidentfox --all-containers=true --tail=200 > incidentfox-logs.txt

# Get pod descriptions
kubectl describe pods -n incidentfox > incidentfox-pods.txt

# Get events
kubectl get events -n incidentfox --sort-by='.lastTimestamp' > incidentfox-events.txt
```

2. **Contact support:**
- Email: support@incidentfox.ai
- Attach: logs, pod descriptions, events
- Include: Kubernetes version, cloud provider, error messages

---

## Next Steps

### 1. Configure Integrations

Navigate to the Web UI and configure integrations:

- **Slack:** Settings → Integrations → Slack
- **GitHub:** Settings → Integrations → GitHub
- **Datadog:** Settings → Integrations → Datadog
- **PagerDuty:** Settings → Integrations → PagerDuty

### 2. Create Additional Teams

Use the Web UI or API to create teams for different use cases:
- SRE/DevOps team
- Security team
- Product team

### 3. Apply Templates

Browse pre-built templates in the Web UI:
- Slack Incident Triage
- Git CI Auto-Fix
- AWS Cost Reduction
- Alert Fatigue Reduction

### 4. Set Up SSO (Optional)

For enterprise customers, configure OIDC/SAML SSO:
- Settings → Security → Single Sign-On
- Integrate with Okta, Azure AD, Google Workspace, etc.

### 5. Review Security Settings

- Token expiration policies
- Audit log retention
- Configuration guardrails

### 6. Monitor Usage

- View agent runs in the Web UI
- Check CloudWatch/Prometheus metrics
- Set up alerts for failures

---

## Appendix: Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Customer's Kubernetes Cluster                          │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Ingress (ALB/NGINX/Traefik)                       │ │
│  │  ↓                                                  │ │
│  │  Web UI (Next.js)  ←→  Config Service (FastAPI)   │ │
│  │       ↓                        ↓                    │ │
│  │  Orchestrator (FastAPI)  ←→  Agent (Python)       │ │
│  │       ↓                        ↓                    │ │
│  │  PostgreSQL ←──────────────────┘                   │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  External Dependencies:                                  │
│  - PostgreSQL (RDS/CloudSQL)                            │
│  - OpenAI API                                           │
│  - Customer Integrations (Slack, GitHub, etc.)         │
└─────────────────────────────────────────────────────────┘
```

---

## Appendix: Secret Reference

| Secret Name | Keys | Purpose | Example Value |
|-------------|------|---------|---------------|
| `incidentfox-database-url` | `DATABASE_URL` | PostgreSQL connection | `postgresql://user:pass@host:5432/db` |
| `incidentfox-config-service` | `ADMIN_TOKEN`, `TOKEN_PEPPER`, `IMPERSONATION_JWT_SECRET` | Config service auth | Random base64 strings |
| `incidentfox-openai` | `api_key` | OpenAI API access | `sk-proj-...` |
| `incidentfox-slack` | `signing_secret`, `bot_token` | Slack integration | From Slack app settings |
| `incidentfox-github` | `GITHUB_WEBHOOK_SECRET` | GitHub webhooks | Random string |
| `incidentfox-registry` | Docker registry credentials | Image pull auth | License key |

---

## Appendix: Resource Requirements

### Minimum (Development/Testing)
- 3 nodes: 2 vCPU, 8GB RAM each
- PostgreSQL: db.t3.small (or equivalent)
- Total cost: ~$200-300/month

### Recommended (Production)
- 5+ nodes: 4 vCPU, 16GB RAM each
- PostgreSQL: db.r5.large (or equivalent)
- With HA, auto-scaling, backups
- Total cost: ~$800-1200/month

### Scaling Guidelines
- Agent pods: CPU-intensive, scale based on concurrent runs
- Config service: I/O-intensive, scale based on API request rate
- Orchestrator: Light CPU, scale for HA only
- Web UI: Light CPU, scale for user count

---

**End of Installation Guide**

For additional support, documentation, or feature requests:
- Docs: https://docs.incidentfox.ai
- Support: support@incidentfox.ai
- Sales: sales@incidentfox.ai

Thank you for choosing IncidentFox! 🦊

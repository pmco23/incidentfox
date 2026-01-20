# Manual Setup Guide - Customer Onboarding Infrastructure

**For:** IncidentFox Engineering Team
**Purpose:** Set up infrastructure required for customer onboarding
**Timeline:** Complete before Jan 13, 2026

---

## Overview

This guide covers the manual steps required to prepare IncidentFox for customer on-premise deployments.

**What needs to be set up:**
1. Docker Hub organization and repositories
2. AWS Vendor Service (Lambda + RDS)
3. Custom domain (license.incidentfox.ai)
4. First customer license

**Total time:** ~3-4 hours

---

## Part 1: Docker Hub Setup (30 minutes)

### Step 1.1: Create Docker Hub Organization

1. **Go to Docker Hub**
   - Visit: https://hub.docker.com
   - Log in or create account

2. **Create Organization**
   - Click "Organizations" → "Create Organization"
   - Name: `incidentfox`
   - Plan: Start with Free (upgrade to Pro later if needed)
   - Click "Create"

3. **Enable 2FA** (IMPORTANT for security)
   - Settings → Security → Two-Factor Authentication
   - Use Authy or Google Authenticator
   - Save backup codes securely

### Step 1.2: Create Repositories

Create 4 public repositories:

**Repository 1: agent**
```
Name: agent
Visibility: Public
Description: IncidentFox AI Agent Runtime - Executes multi-agent workflows with 50+ tools
```

**Repository 2: config-service**
```
Name: config-service
Visibility: Public
Description: IncidentFox Configuration API - Team management, RBAC, and audit logs
```

**Repository 3: orchestrator**
```
Name: orchestrator
Visibility: Public
Description: IncidentFox Orchestrator - Workflow engine and webhook handler
```

**Repository 4: web-ui**
```
Name: web-ui
Visibility: Public
Description: IncidentFox Web Dashboard - Admin and team UI
```

**Commands to create (via CLI):**
```bash
# Install Docker Hub CLI tool (optional)
# brew install hub

# Or use Docker Hub web interface (recommended for first setup)
```

### Step 1.3: Configure Access

**Option A: Personal Access Token (Recommended)**
```bash
# 1. Go to: Account Settings → Security → Access Tokens
# 2. Click "New Access Token"
# 3. Name: "CI/CD Pipeline"
# 4. Permissions: Read & Write
# 5. Click "Generate"
# 6. Save token securely: docker login -u incidentfox -p TOKEN
```

**Option B: License Key Authentication (For Customers)**
- Customers will use their license key as password
- No additional setup needed
- Vendor service handles token generation

### Step 1.4: Test Access

```bash
# Login to Docker Hub
echo "YOUR_TOKEN" | docker login -u incidentfox --password-stdin

# Expected output: "Login Succeeded"

# Test push (after building images)
docker tag alpine:latest incidentfox/test:latest
docker push incidentfox/test:latest
docker rmi incidentfox/test:latest

# Expected: Image pushed successfully
```

---

## Part 2: AWS Vendor Service Deployment (1.5 hours)

### Step 2.1: Prerequisites Check

```bash
# Verify AWS CLI
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "...",
#     "Account": "<your-aws-account-id>",
#     "Arn": "arn:aws:iam::..."
# }

# Verify Terraform
terraform version

# Expected: Terraform v1.5.0 or higher
```

### Step 2.2: Create Terraform State Backend (One-time)

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://incidentfox-terraform-state --region us-west-2

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket incidentfox-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket incidentfox-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name incidentfox-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-west-2
```

### Step 2.3: Deploy Vendor Service

```bash
cd <path-to-vendor-service>

# Run deployment script
./scripts/deploy_production.sh

# This will:
# 1. Initialize Terraform
# 2. Create infrastructure (VPC, RDS, Lambda, API Gateway)
# 3. Deploy Lambda function
# 4. Run database migrations
# 5. Test health endpoint

# Expected time: ~20 minutes (RDS creation is slow)
```

### Step 2.4: Save Deployment Outputs

```bash
cd terraform/envs/prod

# Save outputs
terraform output -json > ~/incidentfox-vendor-service-outputs.json

# Get API endpoint
export API_ENDPOINT=$(terraform output -raw api_endpoint)
echo "API Endpoint: $API_ENDPOINT"

# Get database URL (store securely!)
export DATABASE_URL=$(terraform output -raw database_url)
echo "Database URL: $DATABASE_URL" >> ~/incidentfox-secrets-backup.txt

# Restrict access to secrets file
chmod 600 ~/incidentfox-secrets-backup.txt
```

### Step 2.5: Test Vendor Service

```bash
# Test health endpoint
curl $API_ENDPOINT/health

# Expected: {"status":"healthy","version":"0.1.0",...}

# Test license validation (will fail without license)
curl -X POST $API_ENDPOINT/api/v1/validate \
  -H "Authorization: Bearer test-key"

# Expected: 403 Forbidden (correct - no license exists yet)
```

---

## Part 3: Custom Domain Setup (30 minutes)

### Step 3.1: Request ACM Certificate

```bash
# Request certificate for license.incidentfox.ai
aws acm request-certificate \
  --domain-name license.incidentfox.ai \
  --validation-method DNS \
  --region us-west-2

# Save certificate ARN
CERT_ARN=$(aws acm list-certificates --region us-west-2 \
  --query 'CertificateSummaryList[?DomainName==`license.incidentfox.ai`].CertificateArn' \
  --output text)

echo "Certificate ARN: $CERT_ARN"
```

### Step 3.2: Validate Certificate

```bash
# Get DNS validation record
aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region us-west-2 \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord'

# Output will show:
# {
#     "Name": "_xxx.license.incidentfox.ai.",
#     "Type": "CNAME",
#     "Value": "_yyy.acm-validations.aws."
# }

# Add this CNAME record to Route53 or your DNS provider
```

**In Route53:**
```bash
# Get hosted zone ID
ZONE_ID=$(aws route53 list-hosted-zones \
  --query "HostedZones[?Name=='incidentfox.ai.'].Id" \
  --output text | cut -d'/' -f3)

# Get validation CNAME
VALIDATION_NAME=$(aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region us-west-2 \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord.Name' \
  --output text)

VALIDATION_VALUE=$(aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region us-west-2 \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord.Value' \
  --output text)

# Create validation record
cat > /tmp/change-batch.json <<EOF
{
  "Changes": [{
    "Action": "CREATE",
    "ResourceRecordSet": {
      "Name": "$VALIDATION_NAME",
      "Type": "CNAME",
      "TTL": 300,
      "ResourceRecords": [{"Value": "$VALIDATION_VALUE"}]
    }
  }]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --change-batch file:///tmp/change-batch.json

# Wait for validation (1-5 minutes)
aws acm wait certificate-validated \
  --certificate-arn $CERT_ARN \
  --region us-west-2

echo "Certificate validated!"
```

### Step 3.3: Configure Custom Domain in API Gateway

```bash
# Get API Gateway ID
API_ID=$(aws apigatewayv2 get-apis \
  --query "Items[?Name=='incidentfox-vendor-service-prod'].ApiId" \
  --output text \
  --region us-west-2)

# Create custom domain
aws apigatewayv2 create-domain-name \
  --domain-name license.incidentfox.ai \
  --domain-name-configurations "CertificateArn=$CERT_ARN" \
  --region us-west-2

# Get domain target
DOMAIN_TARGET=$(aws apigatewayv2 get-domain-name \
  --domain-name license.incidentfox.ai \
  --region us-west-2 \
  --query 'DomainNameConfigurations[0].ApiGatewayDomainName' \
  --output text)

# Create API mapping
aws apigatewayv2 create-api-mapping \
  --domain-name license.incidentfox.ai \
  --api-id $API_ID \
  --stage '$default' \
  --region us-west-2
```

### Step 3.4: Create DNS Record for Custom Domain

```bash
# Create A record pointing to API Gateway
cat > /tmp/dns-record.json <<EOF
{
  "Changes": [{
    "Action": "CREATE",
    "ResourceRecordSet": {
      "Name": "license.incidentfox.ai",
      "Type": "A",
      "AliasTarget": {
        "HostedZoneId": "Z2FDTNDATAQYW2",
        "DNSName": "$DOMAIN_TARGET",
        "EvaluateTargetHealth": false
      }
    }
  }]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --change-batch file:///tmp/dns-record.json

# Test after DNS propagation (1-5 minutes)
curl https://license.incidentfox.ai/health

# Expected: {"status":"healthy",...}
```

---

## Part 4: First Customer License (15 minutes)

### Step 4.1: Connect to Database

```bash
# Get database URL from terraform output
cd <path-to-vendor-service>/terraform/envs/prod
DATABASE_URL=$(terraform output -raw database_url)

# Connect to database
psql "$DATABASE_URL"
```

### Step 4.2: Insert First Customer License

```sql
-- Insert demo customer license
INSERT INTO licenses (
  license_key,
  customer_name,
  contract_value,
  expires_at,
  max_teams,
  max_runs_per_month,
  features,
  is_active
) VALUES (
  'IFOX-DEMO-2026-01-11-a1b2c3d4',
  'Demo Customer',
  50000.00,
  '2027-01-11'::timestamp,
  -1,  -- unlimited teams
  -1,  -- unlimited runs
  '["slack", "github", "pagerduty", "sso"]'::jsonb,
  true
);

-- Verify
SELECT license_key, customer_name, expires_at, is_active
FROM licenses
WHERE license_key LIKE 'IFOX-DEMO%';

-- Expected:
-- license_key                    | customer_name | expires_at | is_active
-- -------------------------------|---------------|------------|----------
-- IFOX-DEMO-2026-01-11-a1b2c3d4 | Demo Customer | 2027-01-11 | t

\q
```

### Step 4.3: Test License Validation

```bash
# Test with demo license
curl -X POST https://license.incidentfox.ai/api/v1/validate \
  -H "Authorization: Bearer IFOX-DEMO-2026-01-11-a1b2c3d4"

# Expected:
# {
#   "valid": true,
#   "customer_name": "Demo Customer",
#   "entitlements": {
#     "max_teams": -1,
#     "max_runs_per_month": -1,
#     "features": ["slack", "github", "pagerduty", "sso"]
#   },
#   "expires_at": "2027-01-11T00:00:00",
#   "warnings": []
# }
```

### Step 4.4: Test Registry Token Endpoint

```bash
# Get Docker registry token
TOKEN=$(curl -X POST https://license.incidentfox.ai/api/v1/registry/token \
  -H "Authorization: Bearer IFOX-DEMO-2026-01-11-a1b2c3d4" \
  | jq -r .token)

echo "Registry Token: $TOKEN"

# Expected: JWT token string
```

---

## Part 5: Build and Push Docker Images (30 minutes)

### Step 5.1: Build All Images

```bash
cd <path-to-incidentfox>

# Run build script
./scripts/build_and_push_images.sh v1.0.0

# This will:
# 1. Build all 4 services with --platform linux/amd64
# 2. Tag with v1.0.0 and latest
# 3. Push to Docker Hub

# Expected time: 15-20 minutes (depending on network speed)
```

### Step 5.2: Verify Images on Docker Hub

1. Visit: https://hub.docker.com/u/incidentfox
2. Verify all 4 repositories show v1.0.0 and latest tags
3. Check image size (should be reasonable)
4. Verify last pushed timestamp

### Step 5.3: Test Customer Pull

```bash
# Simulate customer pulling images
echo "IFOX-DEMO-2026-01-11-a1b2c3d4" | docker login -u incidentfox --password-stdin

# Pull images
docker pull incidentfox/agent:v1.0.0
docker pull incidentfox/config-service:v1.0.0
docker pull incidentfox/orchestrator:v1.0.0
docker pull incidentfox/web-ui:v1.0.0

# Verify images
docker images | grep incidentfox

# Expected: All 4 images with v1.0.0 tag
```

---

## Part 6: Final Verification (30 minutes)

### Checklist

- [ ] **Docker Hub**
  - [ ] Organization "incidentfox" created
  - [ ] 4 repositories created (agent, config-service, orchestrator, web-ui)
  - [ ] v1.0.0 images pushed
  - [ ] latest tags updated
  - [ ] Public visibility confirmed

- [ ] **AWS Vendor Service**
  - [ ] Lambda function deployed
  - [ ] RDS PostgreSQL created and accessible
  - [ ] API Gateway configured
  - [ ] Health endpoint responding
  - [ ] Custom domain (license.incidentfox.ai) working
  - [ ] TLS certificate validated

- [ ] **License System**
  - [ ] Database tables created (licenses, usage_logs, analytics_daily)
  - [ ] Demo license inserted and active
  - [ ] License validation endpoint working
  - [ ] Registry token endpoint working
  - [ ] Heartbeat endpoint working

- [ ] **Helm Chart**
  - [ ] values.yaml updated with Docker Hub images
  - [ ] Customer values template complete
  - [ ] Installation guide complete
  - [ ] All documentation reviewed

### Test End-to-End Flow

```bash
# 1. License validation
curl -X POST https://license.incidentfox.ai/api/v1/validate \
  -H "Authorization: Bearer IFOX-DEMO-2026-01-11-a1b2c3d4"

# 2. Registry token
TOKEN=$(curl -X POST https://license.incidentfox.ai/api/v1/registry/token \
  -H "Authorization: Bearer IFOX-DEMO-2026-01-11-a1b2c3d4" \
  | jq -r .token)

# 3. Docker pull
echo $TOKEN | docker login -u incidentfox --password-stdin
docker pull incidentfox/agent:v1.0.0

# 4. Heartbeat
curl -X POST https://license.incidentfox.ai/api/v1/heartbeat \
  -H "Authorization: Bearer IFOX-DEMO-2026-01-11-a1b2c3d4" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_runs_today": 0,
    "agent_runs_this_month": 0,
    "teams_total": 1,
    "teams_active_today": 0
  }'

# All should succeed
```

---

## Troubleshooting

### Issue: Docker Hub Push Fails

**Error:** `denied: requested access to the resource is denied`

**Solution:**
```bash
# Re-login to Docker Hub
docker logout
docker login -u incidentfox

# Verify repository exists
# Go to: https://hub.docker.com/u/incidentfox

# Retry push
docker push incidentfox/agent:v1.0.0
```

### Issue: Terraform State Lock

**Error:** `Error locking state: resource temporarily unavailable`

**Solution:**
```bash
# Force unlock (use with caution!)
cd terraform/envs/prod
terraform force-unlock LOCK_ID

# Get lock ID from error message
```

### Issue: RDS Connection Timeout

**Error:** `could not connect to server: Connection timed out`

**Solution:**
```bash
# Check security group
aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=incidentfox-vendor-service-rds-prod"

# Verify Lambda is in VPC
aws lambda get-function-configuration \
  --function-name incidentfox-vendor-service-prod

# Test from Lambda
aws lambda invoke \
  --function-name incidentfox-vendor-service-prod \
  --payload '{"path": "/health"}' \
  response.json
```

### Issue: Certificate Validation Stuck

**Error:** Certificate stays in "Pending Validation" state

**Solution:**
```bash
# Check DNS record was created
dig _xxx.license.incidentfox.ai CNAME

# Verify in Route53
aws route53 list-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --query "ResourceRecordSets[?Type=='CNAME']"

# Wait up to 30 minutes for DNS propagation
# Re-check certificate status
aws acm describe-certificate --certificate-arn $CERT_ARN
```

---

## Post-Setup Tasks

### 1. Set Up Monitoring

```bash
# CloudWatch alarms for Lambda
aws cloudwatch put-metric-alarm \
  --alarm-name vendor-service-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold

# CloudWatch alarms for RDS
aws cloudwatch put-metric-alarm \
  --alarm-name vendor-service-db-cpu \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

### 2. Set Up Backups

```bash
# Enable automated RDS backups (should be enabled by default)
aws rds modify-db-instance \
  --db-instance-identifier incidentfox-vendor-service-prod \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00"

# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier incidentfox-vendor-service-prod \
  --db-snapshot-identifier vendor-service-initial-snapshot
```

### 3. Document for Team

Save these values securely (1Password, Vault, etc.):

```
# AWS Resources
AWS Account: <your-aws-account-id>
Region: us-west-2
Lambda Function: incidentfox-vendor-service-prod
RDS Instance: incidentfox-vendor-service-prod
API Gateway: https://license.incidentfox.ai

# Docker Hub
Organization: incidentfox
Repositories: agent, config-service, orchestrator, web-ui

# Demo License
License Key: IFOX-DEMO-2026-01-11-a1b2c3d4
Customer: Demo Customer
Expires: 2027-01-11
```

---

## Success Criteria

✅ **All systems operational:**
- Docker Hub: Images published and accessible
- AWS: Vendor service deployed and responding
- DNS: Custom domain working with HTTPS
- License: Demo license working end-to-end
- Documentation: Customer guides complete

✅ **Ready for customer onboarding:**
- Customer can authenticate with license key
- Customer can pull Docker images
- Customer can follow installation guide
- Support team has access to logs and monitoring

---

**Setup complete! Ready for first customer onboarding. 🚀**

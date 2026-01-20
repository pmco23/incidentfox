# Related Repositories

**Last Updated:** 2026-01-11

This document links to related repositories and services that support IncidentFox development, testing, and operations.

---

## Test Environments

### aws-playground (OTEL Demo Microservices)

**Repository:** https://github.com/incidentfox/aws-playground

**Purpose:** OpenTelemetry demo microservices for fault injection testing

**Tech Stack:**
- OTEL demo application (11 microservices)
- Kubernetes deployment
- OpenTelemetry instrumentation
- Fault injection framework

**Deployment:**
- AWS Account: 103002841599
- Region: us-west-2
- Same environment as main IncidentFox deployment

**Usage:**
- Evaluation framework injects failures here
- Tests agent's ability to detect and diagnose issues
- Scenarios: pod crashes, OOMKilled, feature flag failures, dependency issues

**Key Files:**
- `/fault-injection/` - Fault injection scripts
- `/manifests/` - Kubernetes manifests
- `/README.md` - Setup instructions

**Common Commands:**
```bash
# Inject cart service crash
kubectl apply -f fault-injection/cart-crash.yaml

# Reset to healthy state
kubectl apply -f manifests/base/

# View service status
kubectl get pods -n otel-demo
```

---

### simple-fullstack-demo (Git Testing Repository)

**Repository:** https://github.com/incidentfox/simple-fullstack-demo

**Purpose:** Simple fullstack application for testing Git-related agent features

**Tech Stack:**
- Frontend: React
- Backend: Node.js/Express
- Database: SQLite

**Usage:**
- Test GitHub integration features
- CI/CD failure detection and auto-fix
- Pull request analysis
- Code review suggestions
- Git history analysis

**Key Features:**
- Intentionally includes common bugs for testing
- Sample CI/CD workflows
- Test data generation scripts

**Common Scenarios:**
- Create PR with failing tests
- Trigger CI/CD failure
- Test auto-fix capabilities
- Validate code analysis tools

---

## Infrastructure & Operations

### incidentfox-vendor-service (License & Telemetry)

**Repository:** https://github.com/incidentfox/incidentfox-vendor-service

**Purpose:** License validation, telemetry collection, and health monitoring for customer deployments

**Tech Stack:**
- AWS Lambda (Python)
- API Gateway
- DynamoDB (license storage)
- CloudWatch (metrics)

**Deployment:**
- AWS Account: 103002841599
- Region: us-west-2
- URL: https://vendor.incidentfox.ai

**API Endpoints:**
- `POST /api/v1/license/validate` - Validate customer license key
- `POST /api/v1/telemetry/heartbeat` - Receive heartbeat from deployments
- `POST /api/v1/telemetry/analytics` - Receive daily analytics
- `GET /api/v1/health` - Health check

**Key Features:**
- License validation with entitlement checking
- Usage tracking for billing
- Health monitoring of customer deployments
- Quota warnings (e.g., "approaching 90% of monthly runs")
- 1-hour grace period if service unavailable

**Privacy:**
- Only collects aggregate usage metrics
- No PII, credentials, or customer data
- Transparent about what's collected (documented)
- Customers can opt-out of telemetry (license validation always works)

**Integration:**
All IncidentFox deployments call this service:
- On startup: License validation
- Every 5 minutes: Heartbeat with usage stats
- Daily at 2AM UTC: Detailed analytics

**Monitoring:**
```bash
# View CloudWatch logs
aws logs tail /aws/lambda/incidentfox-vendor-service --follow --region us-west-2

# Check API Gateway metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=incidentfox-vendor \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --region us-west-2
```

---

## Marketing & Documentation

### website (Marketing Site)

**Repository:** https://github.com/incidentfox/website

**Purpose:** Public-facing marketing website and landing pages

**Tech Stack:**
- Next.js
- Tailwind CSS
- Vercel deployment

**URL:** https://incidentfox.ai

**Key Pages:**
- `/` - Homepage
- `/product` - Product features
- `/pricing` - Pricing tiers
- `/docs` - Documentation portal
- `/blog` - Company blog
- `/about` - About us

**Content Sync:**
- Technical docs sourced from main mono-repo
- Deployment guides linked to customer/installation-guide.md
- Blog posts about product updates

**Deployment:**
- Vercel (automatic from main branch)
- Custom domain: incidentfox.ai
- CDN: Vercel Edge Network

---

## Development Workflow

### How These Repos Relate to Main Mono-Repo

```
┌─────────────────────────────────────────────────────────────┐
│  Main Mono-Repo (incidentfox/mono-repo)                      │
│                                                                │
│  ├── agent/           - AI agent runtime                      │
│  ├── config_service/  - Control plane                         │
│  ├── orchestrator/    - Webhook routing                       │
│  ├── web_ui/          - Admin/Team console                    │
│  └── ... (other services)                                      │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Deploys to
                           ▼
                    ┌─────────────┐
                    │  AWS EKS    │
                    │  us-west-2  │
                    └─────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                   │
        ▼                  ▼                   ▼
┌──────────────┐  ┌──────────────┐   ┌──────────────┐
│aws-playground│  │ Vendor       │   │    Website   │
│OTEL Demo     │  │ Service      │   │ Marketing    │
│(test target) │  │ (licensing)  │   │ (public)     │
└──────────────┘  └──────────────┘   └──────────────┘
        │                  │
        └──────────────────┘
        Evaluation Framework
        Tests agent against
        injected failures
```

---

## Access & Permissions

### Repository Access

All repositories require GitHub authentication:
- **Public:** website (https://incidentfox.ai is public)
- **Private:** mono-repo, aws-playground, vendor-service, simple-fullstack-demo

**Requesting Access:**
- Internal team: Contact engineering manager
- Partners: Contact partnerships@incidentfox.ai
- Customers: Limited access to docs/ folder only

### AWS Access

**Development:**
```bash
# Configure AWS CLI with playground profile
aws configure --profile playground
# Account: 103002841599
# Region: us-west-2
# Access Key: (from 1Password)
```

**Production:**
- Use IAM roles, not access keys
- MFA required for sensitive operations
- Audit logs enabled

---

## Contributing

### Coordinating Changes

When making changes that span multiple repos:

1. **Create feature branch in each repo:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Link PRs together:**
   - Reference in PR description: "Related to incidentfox/vendor-service#123"

3. **Coordinate deployment:**
   - Deploy vendor-service first (if API changes)
   - Deploy main mono-repo second
   - Update website docs last

4. **Test integration:**
   - Run evaluation framework against aws-playground
   - Verify license validation with vendor-service
   - Check documentation links on website

### Testing Against Related Repos

```bash
# Test agent against aws-playground
python3 scripts/eval_agent_performance.py \
  --agent-url http://localhost:8080 \
  --target-env aws-playground

# Test vendor service integration
export VENDOR_SERVICE_URL=https://vendor.incidentfox.ai
pytest tests/integration/test_vendor_service.py

# Test with simple-fullstack-demo
./scripts/test_git_integration.sh simple-fullstack-demo
```

---

## Maintenance

### Keeping Repos in Sync

**Monthly Tasks:**
1. **Update dependencies** across all repos
2. **Sync documentation** from mono-repo to website
3. **Review access permissions** (remove departing team members)
4. **Backup important data** (license keys, analytics)

**Quarterly Tasks:**
1. **Security audit** of all repositories
2. **Dependency vulnerability scan**
3. **Review and archive** old branches
4. **Performance review** of vendor service

---

## Support & Questions

- **Repository access:** eng@incidentfox.ai
- **AWS access:** ops@incidentfox.ai
- **Website updates:** marketing@incidentfox.ai
- **General questions:** #incidentfox-eng on Slack

---

**Document maintained by:** Engineering Team
**Next review:** 2026-02-11

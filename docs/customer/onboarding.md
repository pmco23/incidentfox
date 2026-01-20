# Customer Onboarding - Complete Package

**Version:** 1.0.0
**Status:** Ready for Customer Onboarding (Week of Jan 13, 2026)
**Prepared:** 2026-01-11

---

## Overview

This document provides a complete overview of all customer-facing materials prepared for IncidentFox on-premise deployments.

## Quick Links

| Document | Purpose | Audience |
|----------|---------|----------|
| [Installation Guide](./installation-guide.md) | Step-by-step installation instructions | Customer DevOps/SRE |
| [Values Template](../charts/incidentfox/values.template.yaml) | Helm values configuration template | Customer DevOps |
| [Architecture Doc](../ON_PREM_DEPLOYMENT_STRATEGY.md) | Technical architecture details | Customer architects |

---

## What Customers Get

### 1. Container Images (Docker Hub)

**Images Published:**
- `incidentfox/agent:v1.0.0` - AI agent runtime with 50+ tools
- `incidentfox/config-service:v1.0.0` - Configuration and RBAC API
- `incidentfox/orchestrator:v1.0.0` - Workflow orchestration engine
- `incidentfox/web-ui:v1.0.0` - Admin dashboard and team UI

**Authentication:**
- Customers use their license key to authenticate
- License key acts as Docker registry password
- Example: `echo LICENSE_KEY | docker login -u incidentfox --password-stdin`

### 2. Helm Chart

**Chart Location:** `oci://registry-1.docker.io/incidentfox/incidentfox:0.1.0`

**What It Deploys:**
- 4 core services (8 pods total with 2 replicas each)
- Kubernetes services, ingress, config maps
- Pre-upgrade migration jobs
- Pod disruption budgets for HA
- Optional: HPA, resource limits, security policies

**What Customers Must Provide:**
- PostgreSQL database (RDS, CloudSQL, or self-hosted)
- Kubernetes secrets (8 total - see installation guide)
- Ingress controller (ALB, NGINX, or Traefik)
- TLS certificate
- DNS configuration

### 3. Documentation Package

| File | Lines | Description |
|------|-------|-------------|
| `installation-guide.md` | 900+ | Complete installation walkthrough |
| `values.template.yaml` (in charts/) | 500+ | Annotated Helm values template |
| `ON_PREM_DEPLOYMENT_STRATEGY.md` | 1200+ | Architecture and design decisions |

---

## Installation Summary

### Time Estimate
- **First-time install:** 2-3 hours
- **Subsequent installs:** 30-45 minutes

### Steps Overview
1. **Infrastructure prep** (1-2 hours)
   - Set up Kubernetes cluster
   - Provision PostgreSQL
   - Install ingress controller
   - Configure DNS and TLS

2. **Secret creation** (30 minutes)
   - Create 8 Kubernetes secrets
   - Store admin tokens securely

3. **Docker registry auth** (5 minutes)
   - Authenticate with license key
   - Create imagePullSecret

4. **Helm installation** (15 minutes)
   - Configure values.yaml
   - Run helm install
   - Wait for pods to be ready

5. **Verification** (15 minutes)
   - Test health endpoints
   - Access Web UI
   - Create first team
   - Run test agent

### Prerequisites Checklist

- [x] Kubernetes 1.24+ with 3+ nodes
- [x] PostgreSQL 13+ (connection string ready)
- [x] Ingress controller installed
- [x] Domain name and DNS access
- [x] TLS certificate (ACM or cert-manager)
- [x] OpenAI API key
- [x] IncidentFox license key
- [x] kubectl and helm installed locally

---

## Customer Success Playbook

### Week 1: Installation & Initial Setup
**Goal:** Get IncidentFox running in their cluster

**Day 1-2:** Infrastructure preparation
- Spin up PostgreSQL
- Set up ingress controller
- Configure TLS
- Create DNS records

**Day 3:** Installation
- Create Kubernetes secrets
- Install Helm chart
- Verify deployment

**Day 4-5:** Initial configuration
- Create teams
- Configure integrations (Slack, GitHub, etc.)
- Test agent runs

### Week 2: Template Deployment
**Goal:** Apply pre-built templates to teams

- Browse template marketplace
- Apply flagship templates:
  - Slack Incident Triage
  - Git CI Auto-Fix
  - AWS Cost Reduction
- Customize templates for specific needs

### Week 3: Production Rollout
**Goal:** Production-ready deployment

- Enable SSO/OIDC
- Configure monitoring and alerts
- Set up backup and disaster recovery
- Train team members
- Document runbooks

### Week 4: Optimization
**Goal:** Fine-tune for production workload

- Review agent run metrics
- Optimize resource limits
- Enable auto-scaling
- Configure rate limiting

---

## Support Model

### Tier 1: Self-Service
**Resources:**
- Documentation site: https://docs.incidentfox.ai
- Installation guide (this package)
- Community forum: https://community.incidentfox.ai

### Tier 2: Email Support
**Contact:** support@incidentfox.ai
**Response Time:** 24 hours (business days)
**Coverage:** Installation issues, configuration questions, bug reports

### Tier 3: Premium Support (Enterprise)
**Contact:** Dedicated Slack channel
**Response Time:** 4 hours
**Coverage:** Architecture review, custom integrations, on-call support

---

## Technical Architecture

### Deployment Model

```
┌───────────────────────────────────────────────────────┐
│  Customer's Data Center / Cloud                       │
│                                                        │
│  ┌──────────────────────────────────────────────────┐│
│  │  Kubernetes Cluster                              ││
│  │                                                   ││
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────┐ ││
│  │  │  Web UI    │←→│ Config Svc   │←→│ Postgres│ ││
│  │  │  (2 pods)  │  │  (2 pods)    │  │         │ ││
│  │  └────────────┘  └──────────────┘  └─────────┘ ││
│  │         ↓               ↓                        ││
│  │  ┌────────────┐  ┌──────────────┐               ││
│  │  │Orchestrator│←→│    Agent     │               ││
│  │  │  (2 pods)  │  │  (2 pods)    │               ││
│  │  └────────────┘  └──────────────┘               ││
│  │         ↑                ↑                        ││
│  └─────────┼────────────────┼───────────────────────┘│
│            │                │                         │
│     External Dependencies:                            │
│     - OpenAI API (api.openai.com)                    │
│     - Customer Integrations (Slack, GitHub, etc.)    │
│     - License Validation (license.incidentfox.ai)    │
└───────────────────────────────────────────────────────┘
```

### License Validation Flow

```
Customer Deployment                  IncidentFox Vendor Service
        │                                      │
        ├─(1) On startup─────────────────────→│
        │    Validate license key              │
        │                                      │
        │←─(2) Returns entitlements───────────┤
        │    {max_teams: -1, features: [...]}│
        │                                      │
        ├─(3) Every 5 minutes────────────────→│
        │    Heartbeat (usage metrics)         │
        │                                      │
        │←─(4) Returns quota warnings─────────┤
        │    "Approaching 90% of monthly runs"│
        │                                      │
```

**Key Points:**
- License validation happens every 5 minutes
- 1-hour grace period if vendor service is down
- Usage metrics for billing and support only
- No customer data transmitted (see Privacy section)

### Privacy & Security

**What We Collect:**
- ✅ Usage metrics (run counts, team counts, error counts)
- ✅ Performance metrics (average response times)
- ✅ License validation (expires when, approaching limits)

**What We DON'T Collect:**
- ❌ Customer data (alerts, logs, investigation results)
- ❌ PII (usernames, emails, IP addresses)
- ❌ Conversation content (prompts, agent responses)
- ❌ Credentials (API keys, tokens, passwords)

**Telemetry Opt-Out:**
- Customers can disable telemetry anytime via Settings UI
- License validation always works (not affected by telemetry setting)
- Transparent about what's collected (documented in UI)

---

## Licensing & Commercial Terms

### License Model: Annual Subscription

**Tiers:**
1. **Starter:** $50k/year
   - 5 teams max
   - 10k agent runs/month
   - Email support

2. **Professional:** $150k/year
   - Unlimited teams
   - 50k agent runs/month
   - Slack support
   - SSO/OIDC included

3. **Enterprise:** $300k+/year
   - Unlimited everything
   - 24/7 on-call support
   - Custom integrations
   - Air-gapped deployment support
   - Dedicated CSM

### What's Included in License

- All 4 core services
- All 10 flagship templates
- 50+ pre-built tools
- Regular updates (monthly releases)
- Security patches
- Documentation access
- Community forum access

### What's NOT Included

Customers must provide:
- Kubernetes cluster (their cost)
- PostgreSQL database (their cost)
- OpenAI API credits (their cost, ~$1-5k/month depending on usage)
- Infrastructure costs (compute, storage, networking)

**Estimated Total Cost of Ownership:**
- IncidentFox license: $50k-300k/year
- Infrastructure (AWS/GCP/Azure): $10k-50k/year
- OpenAI credits: $12k-60k/year
- **Total:** $72k-410k/year

---

## Success Metrics

### Week 1 (Installation)
- [ ] Helm chart successfully deployed
- [ ] All 8 pods running (2 replicas each)
- [ ] Web UI accessible via HTTPS
- [ ] First team created
- [ ] First successful agent run

### Week 2 (Adoption)
- [ ] 3+ teams created
- [ ] 2+ templates applied
- [ ] Slack integration configured
- [ ] GitHub integration configured
- [ ] 10+ agent runs completed

### Month 1 (Production)
- [ ] SSO/OIDC enabled
- [ ] 10+ active users
- [ ] 100+ agent runs
- [ ] Monitoring and alerts configured
- [ ] Backup and DR tested

### Quarter 1 (Value)
- [ ] 50+ teams onboarded
- [ ] 1000+ agent runs
- [ ] Measurable incident MTTR reduction
- [ ] Customer satisfaction survey: 8+/10

---

## Troubleshooting Common Issues

### Issue 1: ImagePullBackOff Errors
**Symptom:** Pods stuck in ImagePullBackOff state
**Cause:** Docker registry authentication failed
**Solution:** Recreate imagePullSecret with correct license key
**Time to resolve:** 5 minutes

### Issue 2: Database Connection Failed
**Symptom:** Config service pod crashing with database error
**Cause:** Wrong connection string or network policy
**Solution:** Test database connectivity from pod, fix connection string
**Time to resolve:** 15 minutes

### Issue 3: 503 Service Unavailable
**Symptom:** Web UI returns 503 error
**Cause:** Pods not ready or health checks failing
**Solution:** Check pod logs, verify readiness probes
**Time to resolve:** 10 minutes

### Issue 4: TLS Certificate Errors
**Symptom:** Browser shows "Certificate Invalid" warning
**Cause:** cert-manager failed to issue certificate
**Solution:** Check cert-manager logs, verify DNS challenge
**Time to resolve:** 30 minutes

**Full troubleshooting guide:** See [Installation Guide](./installation-guide.md#troubleshooting)

---

## Deployment Checklist for Sales

Before scheduling customer onboarding:

### Pre-Sales
- [ ] Customer signed contract
- [ ] License key generated
- [ ] Customer added to support portal
- [ ] Kickoff call scheduled

### Technical Prerequisites
- [ ] Customer has Kubernetes cluster (v1.24+)
- [ ] Customer has PostgreSQL ready
- [ ] Customer has OpenAI API key
- [ ] Customer has domain and TLS certificate ready

### Documentation Delivery
- [ ] Send installation guide
- [ ] Send values template
- [ ] Send architecture document
- [ ] Grant access to docs.incidentfox.ai

### Installation Support
- [ ] Day 1: Infrastructure review call
- [ ] Day 3: Installation support call
- [ ] Day 5: Initial configuration call
- [ ] Day 10: Check-in and Q&A

### Post-Installation
- [ ] Verify deployment successful
- [ ] Collect feedback
- [ ] Schedule Week 2 template training
- [ ] Add to customer success dashboard

---

## Next Steps (Internal - IncidentFox Team)

### Immediate (This Week)
1. **Set up Docker Hub organization** ✅
   - Create `incidentfox` organization
   - Enable 2FA
   - Set up access tokens

2. **Deploy vendor service to production** ✅
   - Deploy to AWS Lambda (us-west-2)
   - Configure custom domain: license.incidentfox.ai
   - Add first customer license to database

3. **Tag and push v1.0.0 releases** ✅
   - Build all 4 services with `--platform linux/amd64`
   - Tag as v1.0.0
   - Push to Docker Hub

4. **Test end-to-end installation** ✅
   - Fresh Kubernetes cluster
   - Follow customer installation guide
   - Document any issues

### Short-term (Next 2 Weeks)
- [ ] Create docs.incidentfox.ai website
- [ ] Record installation video walkthrough
- [ ] Create Terraform modules for common scenarios
- [ ] Build customer success dashboard

### Medium-term (Next Month)
- [ ] Implement usage-based billing calculations
- [ ] Build customer portal (view usage, manage license)
- [ ] Create Helm chart repository
- [ ] Set up monitoring for customer deployments

---

## Contact Information

**Sales Questions:**
- Email: sales@incidentfox.ai
- Calendar: https://cal.incidentfox.ai/sales

**Technical Support:**
- Email: support@incidentfox.ai
- Slack: #incidentfox-support (enterprise customers)

**Partnerships:**
- Email: partnerships@incidentfox.ai

**General:**
- Website: https://incidentfox.ai
- Docs: https://docs.incidentfox.ai
- Status: https://status.incidentfox.ai

---

**Document Version:** 1.0.0
**Last Updated:** 2026-01-11
**Next Review:** 2026-02-01

**Prepared by:** IncidentFox Engineering Team
**Approved by:** CTO, VP Sales, Customer Success

---

## Appendix: Files in This Package

```
docs/
├── CUSTOMER_ONBOARDING_README.md        ← This file (overview)
├── installation-guide.md       ← Step-by-step installation
├── ON_PREM_DEPLOYMENT_STRATEGY.md       ← Technical architecture
└── ARCHITECTURE.md                       ← Product architecture

charts/incidentfox/
├── Chart.yaml                            ← Helm chart metadata
├── values.yaml                           ← Default values
├── values.template.yaml                  ← Customer values template
├── values.prod.yaml                      ← Production example
├── templates/                            ← Kubernetes manifests
└── README.md                             ← Chart documentation
```

---

**Ready for customer onboarding! 🚀**

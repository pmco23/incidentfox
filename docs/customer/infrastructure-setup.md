# IncidentFox Infrastructure Setup Guide

**Choose your infrastructure setup path based on your team's situation.**

---

## Decision Tree: Which Path is Right for You?

```
┌─────────────────────────────────────────────────────────────┐
│  Do you already have a Kubernetes cluster (EKS/GKE/AKS)?    │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
       YES                           NO
        │                             │
        ▼                             ▼
┌───────────────────┐      ┌──────────────────────┐
│ Do you have       │      │ Use our Terraform    │
│ Terraform         │      │ to create everything │
│ experience?       │      │                      │
└────────┬──────────┘      │ → PATH 1: Terraform  │
         │                 │   Complete Stack     │
    ┌────┴────┐            └──────────────────────┘
   YES       NO
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│ PATH 2: │ │ PATH 3:      │
│ Bring   │ │ AWS Console  │
│ Your    │ │ Click-Ops    │
│ Own     │ │              │
└─────────┘ └──────────────┘
```

---

## PATH 1: Terraform Complete Stack (Recommended)

**Best for:** DevOps teams starting from scratch

**What you get:**
- ✅ Full AWS infrastructure created automatically
- ✅ VPC with public/private subnets
- ✅ EKS Kubernetes cluster
- ✅ RDS PostgreSQL database
- ✅ Load balancer controller pre-configured
- ✅ Infrastructure as Code (repeatable, version-controlled)

**Time required:** 30 minutes setup + 20 minutes apply

**Cost:** ~$470/month (EKS + RDS + compute)

**Start here:** [customer-terraform/aws/complete/](../customer-terraform/aws/complete/README.md)

---

## PATH 2: Bring Your Own Infrastructure

**Best for:** Teams with existing Kubernetes clusters

**What you need:**
- ✅ Kubernetes cluster (v1.24+)
- ✅ PostgreSQL database (v13+)
- ✅ Ingress controller installed
- ✅ kubectl configured

**Options:**

### Option 2A: Create Database Only (Terraform)
If you have EKS but need a PostgreSQL database:
→ [customer-terraform/aws/minimal/](../customer-terraform/aws/minimal/README.md)

### Option 2B: Skip Infrastructure Setup Entirely
If you have both Kubernetes AND PostgreSQL:
→ Skip to [Helm Installation](./installation-guide.md#phase-4-helm-installation)

---

## PATH 3: AWS Console Setup (No Terraform)

**Best for:** Small teams or those new to Infrastructure as Code

**What you'll do:**
- 📋 Step-by-step AWS Console instructions
- 📸 Screenshots for each step
- 🎯 No coding required

**Time required:** 2-3 hours

**Start here:** [console-guide.md](./console-guide.md)

---

## PATH 4: Managed Installation (Enterprise)

**Best for:** Enterprises who want IncidentFox to handle everything

**What you get:**
- ✅ We deploy in YOUR AWS account
- ✅ We manage infrastructure
- ✅ We handle upgrades
- ✅ White-glove onboarding

**Contact:** IncidentFox

---

## Comparison Matrix

| Feature | PATH 1: Terraform | PATH 2: BYO | PATH 3: Console | PATH 4: Managed |
|---------|-------------------|-------------|-----------------|-----------------|
| **Setup Time** | 30 min | 0-30 min | 2-3 hours | 1 week |
| **Technical Level** | Medium | Low | Low | None |
| **Infrastructure Control** | Full | Full | Full | Limited |
| **Repeatability** | High | Medium | Low | N/A |
| **Cost** | AWS only | AWS only | AWS only | AWS + service fee |
| **Support Level** | Self-service | Self-service | Self-service | Dedicated |

---

## After Infrastructure Setup

Once your infrastructure is ready, continue with:

1. [Helm Installation](./installation-guide.md#phase-4-helm-installation)
2. [Initial Configuration](./installation-guide.md#phase-6-initial-configuration)
3. [Integration Setup](./INTEGRATION_GUIDE.md)

---

## Need Help Deciding?

**Ask yourself:**

1. **Do I have a Kubernetes cluster?**
   - Yes → PATH 2 (BYO)
   - No → Continue

2. **Do I know Terraform?**
   - Yes → PATH 1 (Terraform)
   - No → Continue

3. **Am I comfortable with AWS Console?**
   - Yes → PATH 3 (Console)
   - No → PATH 4 (Managed)

4. **Is this for production?**
   - Yes, large enterprise → PATH 4 (Managed)
   - Yes, small/medium → PATH 1 (Terraform)
   - No, testing/POC → PATH 2 or 3

---

## Support

- 📧 Email: support@incidentfox.ai
- 📖 Docs: [All Documentation](./README.md)
- 💬 Community: community.incidentfox.ai

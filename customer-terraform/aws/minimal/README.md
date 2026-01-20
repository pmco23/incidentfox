# IncidentFox AWS Infrastructure - Minimal Stack (RDS Only)

Creates **only the RDS PostgreSQL database** for IncidentFox.

## Who Should Use This

✅ You already have an EKS/Kubernetes cluster
✅ You already have a VPC with private subnets
✅ You just need a managed PostgreSQL database

## Quick Start

```bash
# 1. Configure
cp terraform.tfvars.example terraform.tfvars
vi terraform.tfvars  # Fill in your VPC ID, security group ID

# 2. Apply
terraform init
terraform apply

# 3. Get connection string
terraform output -raw database_connection_string

# 4. Create Kubernetes secret
terraform output -raw database_secret_create_command | bash
```

## What You Need

Find these values in AWS Console:
- **VPC ID**: AWS Console → VPC → Your VPCs
- **EKS Security Group ID**: AWS Console → EKS → Cluster → Networking tab

## Cost

~$140/month for db.t3.large

## Next Steps

Continue with [Helm Installation](../../../docs/customer/installation-guide.md#phase-4-helm-installation)

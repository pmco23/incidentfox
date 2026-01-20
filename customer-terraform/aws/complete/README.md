# IncidentFox AWS Infrastructure - Complete Stack

This Terraform configuration creates **all required AWS infrastructure** for running IncidentFox:

✅ VPC with public/private subnets across 3 availability zones
✅ EKS Kubernetes cluster with managed node groups
✅ RDS PostgreSQL database (encrypted, automated backups)
✅ IAM roles for AWS Load Balancer Controller
✅ IAM roles for External Secrets Operator (optional)

---

## Who Should Use This

**Use this if:**
- ✅ You're starting from scratch (no existing AWS infrastructure)
- ✅ You want a production-ready, high-availability setup
- ✅ You're comfortable with Terraform

**Don't use this if:**
- ❌ You already have an EKS cluster → Use [../minimal](../minimal) instead
- ❌ You don't have Terraform experience → See [Console Guide](../../../docs/INFRASTRUCTURE_AWS_CONSOLE.md)

---

## Prerequisites

### 1. AWS Account & Credentials

```bash
# Configure AWS CLI with your credentials
aws configure

# Verify access
aws sts get-caller-identity
```

**Required IAM Permissions:**
- VPC management (create VPCs, subnets, route tables)
- EKS cluster creation
- RDS database creation
- IAM role/policy management

### 2. Install Tools

```bash
# Terraform (>= 1.5.0)
brew install terraform  # macOS
# OR
# Download from: https://developer.hashicorp.com/terraform/downloads

# kubectl
brew install kubectl  # macOS

# Helm
brew install helm  # macOS

# Verify installations
terraform version
kubectl version --client
helm version
```

---

## Quick Start

### 1. Configure Your Values

```bash
# Copy the example configuration
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
vi terraform.tfvars
```

**Minimum required changes:**
```hcl
customer_name = "your-company-name"  # Example: "acme-corp"
aws_region    = "us-west-2"
rds_password  = "your-secure-password-min-16-chars"
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review the Plan

```bash
# See what will be created
terraform plan
```

**Expected resources:** ~50 resources will be created including:
- 1 VPC with 6 subnets (3 public, 3 private)
- 1 EKS cluster with 3 worker nodes
- 1 RDS PostgreSQL instance
- Security groups, route tables, IAM roles, etc.

### 4. Apply Configuration

```bash
# Create all infrastructure
terraform apply

# Type 'yes' when prompted
```

**⏱️ Expected duration:** 15-20 minutes
- VPC: ~2 minutes
- EKS: ~12 minutes
- RDS: ~5 minutes

### 5. Get Outputs

```bash
# View all outputs
terraform output

# Get database connection string
terraform output -raw database_connection_string

# Get kubectl configuration command
terraform output -raw eks_configure_kubectl_command
```

---

## Next Steps After Terraform Completes

### 1. Configure kubectl

```bash
# Configure kubectl to access your new EKS cluster
aws eks update-kubeconfig --region us-west-2 --name <your-cluster-name>

# Verify connectivity
kubectl get nodes
```

### 2. Install AWS Load Balancer Controller

```bash
# Add EKS Helm repository
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Get the IAM role ARN
ALB_ROLE_ARN=$(terraform output -raw alb_controller_role_arn)

# Install AWS Load Balancer Controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=$(terraform output -raw eks_cluster_name) \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$ALB_ROLE_ARN

# Verify installation
kubectl get deployment -n kube-system aws-load-balancer-controller
```

### 3. Create Database Secret

```bash
# Create namespace
kubectl create namespace incidentfox

# Create database secret
terraform output -raw database_connection_string_k8s_secret | bash
```

### 4. Continue with Helm Installation

Follow the [Installation Guide](../../../docs/customer/installation-guide.md#phase-4-helm-installation) starting at Phase 4.

---

## Cost Estimation

**Monthly AWS costs** (approximate, us-west-2 region):

| Resource | Configuration | Monthly Cost |
|----------|--------------|--------------|
| EKS Control Plane | 1 cluster | $73 |
| EC2 Nodes | 3x t3.xlarge | $225 |
| RDS PostgreSQL | db.t3.large | $140 |
| Data Transfer | 100GB | $10 |
| Load Balancers | 1 ALB | $20 |
| **TOTAL** | | **~$468/month** |

*Costs vary by region and usage. Use [AWS Pricing Calculator](https://calculator.aws/) for accurate estimates.*

**Cost Optimization Tips:**
- Use Savings Plans or Reserved Instances for 30-50% savings
- Enable RDS auto-scaling for storage
- Use EKS managed node groups with auto-scaling
- Configure cluster autoscaler to scale down during off-hours

---

## Customization

### Scaling Configuration

**For smaller workloads:**
```hcl
eks_node_desired_count = 2
eks_node_instance_types = ["t3.large"]  # 2 vCPU, 8GB RAM
rds_instance_class = "db.t3.medium"     # 2 vCPU, 4GB RAM
```

**For larger workloads:**
```hcl
eks_node_desired_count = 5
eks_node_instance_types = ["t3.2xlarge"]  # 8 vCPU, 32GB RAM
rds_instance_class = "db.r6g.xlarge"      # 4 vCPU, 32GB RAM
```

### Multi-Region Deployment

To deploy in multiple regions, create separate Terraform workspaces:

```bash
# Create workspace for us-east-1
terraform workspace new us-east-1
terraform apply

# Create workspace for eu-west-1
terraform workspace new eu-west-1
terraform apply -var="aws_region=eu-west-1"
```

---

## Troubleshooting

### Issue: Terraform times out creating EKS cluster

**Solution:** EKS creation can take 15-20 minutes. Increase timeout:
```bash
terraform apply -timeout=30m
```

### Issue: kubectl can't connect to cluster

**Solution:** Update kubeconfig:
```bash
aws eks update-kubeconfig --region us-west-2 --name <cluster-name>
```

### Issue: RDS password doesn't meet requirements

**Error:** Password must be at least 16 characters

**Solution:** Generate a strong password:
```bash
openssl rand -base64 24
```

### Issue: VPC CIDR conflicts with existing network

**Solution:** Change VPC CIDR in terraform.tfvars:
```hcl
vpc_cidr = "10.1.0.0/16"  # Use a different range
```

---

## Cleanup / Destruction

**⚠️ WARNING:** This will delete all resources including the database!

```bash
# Review what will be destroyed
terraform plan -destroy

# Destroy all resources
terraform destroy

# Type 'yes' when prompted
```

**Before destroying:**
1. Export any important data from PostgreSQL
2. Remove deletion protection from RDS (if enabled)
3. Delete any manually created resources in the VPC

---

## Support

- 📖 Documentation: [IncidentFox Docs](../../../docs/)
- 💬 Support: support@incidentfox.ai
- 🐛 Issues: [GitHub Issues](https://github.com/incidentfox/incidentfox/issues)

---

## Files in This Directory

- `main.tf` - Main Terraform configuration
- `variables.tf` - Input variables with defaults
- `outputs.tf` - Output values after apply
- `terraform.tfvars.example` - Example configuration
- `README.md` - This file

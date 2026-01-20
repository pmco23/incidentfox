# AWS Infrastructure Setup with Terraform

Quick guide for setting up IncidentFox infrastructure on AWS using Terraform.

---

## Prerequisites

- AWS Account with admin access
- AWS CLI installed and configured
- Terraform >= 1.5.0 installed
- 30 minutes of your time

---

## Quick Start

### 1. Choose Your Configuration

**Option A: Complete Stack** (VPC + EKS + RDS)
→ Best if starting from scratch

**Option B: Minimal Stack** (RDS only)
→ Best if you already have EKS

### 2. Navigate to Configuration

```bash
cd customer-terraform/aws/complete/  # OR cd customer-terraform/aws/minimal/
```

### 3. Configure Your Values

```bash
# Copy the example
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
vi terraform.tfvars
```

**Required values:**
```hcl
customer_name = "your-company"     # Example: "acme-corp"
aws_region    = "us-west-2"        # Your AWS region
rds_password  = "your-secure-password-min-16-chars"
```

### 4. Deploy

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply configuration
terraform apply
```

⏱️ **Wait 15-20 minutes** for resources to be created.

### 5. Get Outputs

```bash
# View all outputs
terraform output

# Get specific values
terraform output -raw database_connection_string
terraform output -raw eks_configure_kubectl_command
```

---

## Next Steps

1. **Configure kubectl** (if using complete stack):
   ```bash
   aws eks update-kubeconfig --region us-west-2 --name <cluster-name>
   ```

2. **Install AWS Load Balancer Controller** (if using complete stack):
   ```bash
   # See complete instructions in:
   # customer-terraform/aws/complete/README.md#next-steps
   ```

3. **Create database secret**:
   ```bash
   kubectl create namespace incidentfox
   terraform output -raw database_secret_create_command | bash
   ```

4. **Continue with Helm**:
   → [Helm Installation Guide](./installation-guide.md#phase-4-helm-installation)

---

## Detailed Documentation

For comprehensive documentation, examples, and troubleshooting:

- **Complete Stack**: [customer-terraform/aws/complete/README.md](../customer-terraform/aws/complete/README.md)
- **Minimal Stack**: [customer-terraform/aws/minimal/README.md](../customer-terraform/aws/minimal/README.md)

---

## Cost Estimate

**Complete Stack:** ~$470/month
- EKS: $73/month
- EC2 nodes: $225/month
- RDS: $140/month
- Networking: $32/month

**Minimal Stack:** ~$140/month
- RDS only

Use [AWS Calculator](https://calculator.aws/) for accurate estimates.

---

## Cleanup

**⚠️ WARNING:** This deletes all resources including data!

```bash
terraform destroy
```

---

## Troubleshooting

### Issue: Terraform times out

**Solution:** Increase timeout:
```bash
terraform apply -timeout=30m
```

### Issue: kubectl can't connect

**Solution:**
```bash
aws eks update-kubeconfig --region us-west-2 --name <cluster-name>
kubectl get nodes
```

### Issue: Password requirements

Generate strong password:
```bash
openssl rand -base64 24
```

---

## Support

- 📧 support@incidentfox.ai
- 📖 [Back to Infrastructure Setup](./infrastructure-setup.md)

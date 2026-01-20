# AWS Infrastructure Setup via Console (Click-Ops)

Step-by-step guide for creating AWS infrastructure using the AWS Console (no Terraform required).

**Time required:** 2-3 hours

---

## Overview

You'll create:
1. VPC with subnets (20 minutes)
2. EKS Kubernetes cluster (30 minutes)
3. RDS PostgreSQL database (15 minutes)
4. Security groups and networking (15 minutes)

---

## Prerequisites

- AWS Account with admin access
- Credit card on file (for AWS billing)
- Pen and paper to write down IDs

---

## Part 1: Create VPC

### Step 1.1: Navigate to VPC Dashboard

1. Log into AWS Console: https://console.aws.amazon.com
2. Select your region (top-right): **us-west-2** recommended
3. Search for "VPC" in top search bar
4. Click "VPC Dashboard"

### Step 1.2: Create VPC

1. Click **"Create VPC"** button
2. Choose **"VPC and more"** (creates subnets automatically)
3. Fill in:
   - **Name**: `incidentfox-vpc`
   - **IPv4 CIDR**: `10.0.0.0/16`
   - **Number of AZs**: `3`
   - **Number of public subnets**: `3`
   - **Number of private subnets**: `3`
   - **NAT gateways**: `1 per AZ` (costs ~$32/month)
   - **VPC endpoints**: `None`
4. Click **"Create VPC"**

⏱️ Wait 2-3 minutes

📝 **Write down:** VPC ID (looks like `vpc-0123abc...`)

---

## Part 2: Create EKS Cluster

### Step 2.1: Navigate to EKS

1. Search for "EKS" in top search bar
2. Click **"Elastic Kubernetes Service"**

### Step 2.2: Create Cluster

1. Click **"Add cluster"** → **"Create"**
2. **Configure cluster:**
   - **Name**: `incidentfox-eks`
   - **Kubernetes version**: `1.29` (latest)
   - **Cluster service role**: Click **"Create new role"**
     - Opens IAM console
     - Service: Select **"EKS - Cluster"**
     - Click **"Next"**, **"Next"**, **"Next"**
     - Name: `incidentfox-eks-cluster-role`
     - Click **"Create role"**
     - Return to EKS tab, click refresh, select the role
   - Click **"Next"**

3. **Specify networking:**
   - **VPC**: Select `incidentfox-vpc`
   - **Subnets**: Select all **private** subnets (should be 3)
   - **Security groups**: Leave default
   - **Cluster endpoint access**: `Public and private`
   - Click **"Next"**

4. **Configure observability**: Click **"Next"** (skip)

5. **Select add-ons**: Leave defaults, click **"Next"**

6. **Review and create**: Click **"Create"**

⏱️ Wait 12-15 minutes for cluster creation

📝 **Write down:** Cluster name (`incidentfox-eks`)

### Step 2.3: Create Node Group

Once cluster status is "Active":

1. Go to **"Compute"** tab
2. Click **"Add node group"**
3. **Configure node group:**
   - **Name**: `incidentfox-nodes`
   - **Node IAM role**: Click **"Create new role"**
     - Service: Select **"EC2"**
     - Policies: Attach these 3 policies:
       - `AmazonEKSWorkerNodePolicy`
       - `AmazonEKS_CNI_Policy`
       - `AmazonEC2ContainerRegistryReadOnly`
     - Name: `incidentfox-eks-node-role`
     - Click **"Create role"**
   - Return to EKS, refresh, select the role
   - Click **"Next"**

4. **Set compute and scaling:**
   - **AMI type**: `Amazon Linux 2`
   - **Instance types**: `t3.xlarge` (4 vCPU, 16GB RAM)
   - **Disk size**: `50` GB
   - **Desired size**: `3`
   - **Minimum size**: `3`
   - **Maximum size**: `6`
   - Click **"Next"**

5. **Specify networking**: Leave defaults, click **"Next"**

6. **Review and create**: Click **"Create"**

⏱️ Wait 5-10 minutes

📝 **Write down:** Node group security group ID (found in Networking tab)

---

## Part 3: Create RDS PostgreSQL Database

### Step 3.1: Navigate to RDS

1. Search for "RDS" in top search bar
2. Click **"RDS Dashboard"**
3. Click **"Create database"**

### Step 3.2: Configure Database

1. **Engine options:**
   - **Engine type**: `PostgreSQL`
   - **Engine version**: `PostgreSQL 15.4-R2` (latest)

2. **Templates**: Select **"Production"**

3. **Settings:**
   - **DB instance identifier**: `incidentfox-db`
   - **Master username**: `incidentfox`
   - **Master password**: Generate strong password
     - Click **"Auto generate a password"**
     - OR enter your own (min 16 chars)
   - **Confirm password**: (enter again)

   📝 **Write down:** Master password (keep secure!)

4. **Instance configuration:**
   - **DB instance class**: `Burstable classes`
   - **Instance type**: `db.t3.large` (2 vCPU, 8GB RAM)

5. **Storage:**
   - **Storage type**: `General Purpose SSD (gp3)`
   - **Allocated storage**: `100` GB
   - **Enable storage autoscaling**: ✅ Checked
   - **Maximum storage threshold**: `1000` GB

6. **Connectivity:**
   - **Compute resource**: `Don't connect to an EC2 compute resource`
   - **VPC**: Select `incidentfox-vpc`
   - **Public access**: **No**
   - **VPC security group**: **Create new**
     - Name: `incidentfox-db-sg`
   - **Availability Zone**: `No preference`

7. **Database authentication**: `Password authentication`

8. **Additional configuration** (expand section):
   - **Initial database name**: `incidentfox`
   - **Backup retention**: `7` days
   - **Enable deletion protection**: ✅ Checked

9. Click **"Create database"**

⏱️ Wait 5-10 minutes

📝 **Write down:**
- DB endpoint (looks like `incidentfox-db.abc123.us-west-2.rds.amazonaws.com`)
- Security group ID (from Connectivity tab)

---

## Part 4: Configure Security Groups

### Step 4.1: Allow EKS to Access RDS

1. Go to **EC2 Console** → **Security Groups**
2. Find `incidentfox-db-sg` security group
3. Click on it, go to **"Inbound rules"** tab
4. Click **"Edit inbound rules"**
5. Click **"Add rule"**:
   - **Type**: `PostgreSQL`
   - **Port**: `5432`
   - **Source**: Select the EKS node security group (from Part 2.3)
   - **Description**: `Allow EKS nodes to access database`
6. Click **"Save rules"**

---

## Part 5: Install AWS Load Balancer Controller

### Step 5.1: Configure kubectl

On your local machine:

```bash
# Install kubectl (if not installed)
brew install kubectl  # macOS
# OR download from: https://kubernetes.io/docs/tasks/tools/

# Configure kubectl to access your cluster
aws eks update-kubeconfig --region us-west-2 --name incidentfox-eks

# Verify connection
kubectl get nodes
```

Expected output: 3 nodes in "Ready" state

### Step 5.2: Create IAM OIDC Provider

```bash
# Get cluster OIDC issuer URL
CLUSTER_NAME=incidentfox-eks
OIDC_ID=$(aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.identity.oidc.issuer" --output text | cut -d '/' -f 5)

# Check if OIDC provider exists
aws iam list-open-id-connect-providers | grep $OIDC_ID

# If not found, create it
eksctl utils associate-iam-oidc-provider --cluster $CLUSTER_NAME --approve
```

### Step 5.3: Install AWS Load Balancer Controller

```bash
# Download IAM policy
curl -O https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.0/docs/install/iam_policy.json

# Create IAM policy
aws iam create-policy \
    --policy-name AWSLoadBalancerControllerIAMPolicy \
    --policy-document file://iam_policy.json

# Create service account
eksctl create iamserviceaccount \
  --cluster=incidentfox-eks \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --role-name AmazonEKSLoadBalancerControllerRole \
  --attach-policy-arn=arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:policy/AWSLoadBalancerControllerIAMPolicy \
  --approve

# Install controller via Helm
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=incidentfox-eks \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller

# Verify installation
kubectl get deployment -n kube-system aws-load-balancer-controller
```

---

## Part 6: Create Kubernetes Secret for Database

```bash
# Create namespace
kubectl create namespace incidentfox

# Create database secret
kubectl create secret generic incidentfox-database-url \
  --from-literal=DATABASE_URL="postgresql://incidentfox:<YOUR_PASSWORD>@<DB_ENDPOINT>/incidentfox" \
  -n incidentfox

# Verify
kubectl get secret incidentfox-database-url -n incidentfox
```

Replace:
- `<YOUR_PASSWORD>`: Master password from Part 3.2
- `<DB_ENDPOINT>`: DB endpoint from Part 3.2

---

## Summary: What You Created

✅ **VPC** (`vpc-0123abc...`)
✅ **EKS Cluster** (`incidentfox-eks`)
✅ **EKS Node Group** (3 nodes)
✅ **RDS PostgreSQL** (`incidentfox-db`)
✅ **Security Groups** (configured)
✅ **AWS Load Balancer Controller** (installed)
✅ **Kubernetes Secret** (database URL)

---

## Next Steps

Continue with IncidentFox installation:

→ [Helm Installation Guide](./installation-guide.md#phase-4-helm-installation)

---

## Estimated Costs

- **EKS Cluster**: $73/month
- **EC2 Nodes** (3x t3.xlarge): $225/month
- **RDS** (db.t3.large): $140/month
- **NAT Gateways** (3): $32/month
- **Load Balancer**: $20/month

**Total**: ~$490/month

---

## Troubleshooting

### Issue: Can't find VPC in EKS setup

**Solution:** Make sure you're in the same AWS region for all steps

### Issue: kubectl can't connect to cluster

**Solution:**
```bash
aws eks update-kubeconfig --region us-west-2 --name incidentfox-eks
kubectl get nodes
```

### Issue: Nodes not appearing

**Solution:** Check node group status in EKS Console → Compute tab

---

## Support

- 📧 support@incidentfox.ai
- 📖 [Back to Infrastructure Setup](./infrastructure-setup.md)

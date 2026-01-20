# RAPTOR Knowledge Base - AWS Infrastructure

This directory contains Terraform configuration for deploying the RAPTOR Knowledge Base API to AWS.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           VPC (Private)                          │
│                                                                  │
│   ┌──────────────────┐                                          │
│   │  Internal ALB    │ ←── Other services (web_ui, agent)       │
│   │  (HTTP :80)      │                                          │
│   └────────┬─────────┘                                          │
│            │                                                     │
│            ▼                                                     │
│   ┌──────────────────┐     ┌──────────────────┐                 │
│   │  ECS Fargate     │     │  S3 Bucket       │                 │
│   │  (ARM64/Graviton)│◄────│  (Tree Files)    │                 │
│   │                  │     │  mega_ultra_v2   │                 │
│   │  raptor-kb:8000  │     └──────────────────┘                 │
│   └──────────────────┘                                          │
│            │                                                     │
│            ▼                                                     │
│   ┌──────────────────┐     ┌──────────────────┐                 │
│   │  CloudWatch Logs │     │  Secrets Manager │                 │
│   │                  │     │  (OpenAI Key)    │                 │
│   └──────────────────┘     └──────────────────┘                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Resources Created

| Resource | Description |
|----------|-------------|
| ECS Cluster | `raptor-kb-production` |
| ECS Service | Fargate service with 1 task (ARM64) |
| ECR Repository | Docker image storage |
| Internal ALB | HTTP load balancer (VPC-only access) |
| S3 Bucket | Tree file storage (1.5GB+ per tree) |
| Secrets Manager | OpenAI API key |
| CloudWatch | Logs and alarms |
| IAM Roles | Task execution and runtime permissions |

## Prerequisites

1. AWS CLI configured with `playground` profile
2. Terraform >= 1.0
3. Docker with buildx (for ARM64 builds)
4. Terraform state bucket exists: `incidentfox-terraform-state`

## Deployment Steps

### 1. Initialize Terraform

```bash
cd knowledge_base/infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your OpenAI API key

terraform init
terraform plan
terraform apply
```

### 2. Deploy the Application

```bash
cd knowledge_base
./scripts/deploy.sh
```

This will:
- Upload tree files to S3
- Build and push Docker image to ECR
- Trigger ECS service update

### 3. Configure Web UI

Add the ALB URL to your web_ui environment:

```bash
# Get the URL
cd knowledge_base/infra/terraform
terraform output web_ui_env_var

# Add to web_ui/.env.local
RAPTOR_API_URL=http://internal-raptor-kb-xxxxx.us-west-2.elb.amazonaws.com
```

## Updating Tree Files

To update the mega_ultra_v2 tree or add new trees:

```bash
# Upload to S3
aws s3 sync trees/ s3://raptor-kb-trees-ACCOUNT_ID/trees/ --profile playground

# Restart service to pick up new trees
aws ecs update-service --cluster raptor-kb-production --service raptor-kb --force-new-deployment
```

## Monitoring

```bash
# View logs
aws logs tail /ecs/raptor-kb-production --follow --profile playground

# Check service status
aws ecs describe-services --cluster raptor-kb-production --services raptor-kb --profile playground

# Check target health
aws elbv2 describe-target-health --target-group-arn <TG_ARN> --profile playground
```

## Costs

Estimated monthly costs (us-west-2):
- ECS Fargate (2 vCPU, 8GB): ~$100/month
- ALB: ~$20/month
- S3 (2GB): ~$0.05/month
- CloudWatch Logs: ~$5/month
- **Total: ~$125/month**

## Troubleshooting

### Container won't start
- Check CloudWatch logs for startup errors
- Verify OpenAI API key in Secrets Manager
- Ensure S3 bucket has tree files

### Tree loading is slow
- First startup downloads 1.5GB from S3 (~30s on good network)
- Subsequent startups use cached image layers
- Consider increasing `startPeriod` in health check if needed

### Out of memory
- Tree loading requires ~3-4GB RAM
- Current config: 8GB (leaves headroom for embeddings)
- Increase `memory` variable if needed


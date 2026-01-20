# `infra/terraform/` — IncidentFox AWS Infrastructure (EKS/RDS/IRSA)

This directory is the **AWS-side infrastructure** for customer deployments on **AWS + EKS**.

We support two modes:
- **BYO** (bring your own): customer provides EKS cluster (and optionally RDS). We provision only what we must on AWS (IRSA roles/policies, optional RDS).
- **Managed**: we create EKS + RDS + required IAM for controllers, then deploy apps via Helm.

> Helm/Kubernetes resources live under `charts/`. Terraform should manage AWS resources (RDS, IAM, optional EKS), not in-cluster objects.

## Remote state (enterprise default)

We standardize on Terraform remote state with:
- **S3 bucket** for state
- **DynamoDB table** for state locking

Because Terraform backends are configured **before** Terraform runs, the state bucket/table must be bootstrapped once per account/region.

### Bootstrap state bucket/table (one-time)

Use `infra/terraform/state-bootstrap/` to create:
- S3 bucket
- DynamoDB lock table

Then set the backend config for each env under `infra/terraform/envs/<env>/`.

## Environments

- `envs/dev/`: dev/test stack (can create EKS/RDS, or target existing)

## Modules

- `modules/eks/`: EKS cluster creation (optional)
- `modules/rds/`: Postgres RDS creation (optional)
- `modules/iam_irsa/`: IRSA roles/policies for:
  - AWS Load Balancer Controller (ALB)
  - External Secrets Operator (ESO)

## Deployment flow (high level)

1) Terraform apply (AWS infra)
2) Install controllers (ALB controller + ESO) via Helm
3) Helm install/upgrade IncidentFox umbrella chart (`charts/incidentfox/`)

The recommended entrypoint is the deploy CLI:
- `scripts/incidentfoxctl.py`



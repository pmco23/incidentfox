# IncidentFox EKS Pilot Runbook (new region, clean slate)

Goal: create a clean “happy path” deployment in a fresh AWS region, without touching existing resources.

## Recommended pilot region

Use a new region for the pilot (example: `us-east-1`) to avoid mixing with prior experiments in `us-west-2`.

## Prereqs

- `aws` CLI configured (account + permissions to create EKS/RDS/IAM/ECR/S3/DynamoDB/Secrets Manager)
- `terraform >= 1.6`, `kubectl`, `helm`

## 1) Bootstrap Terraform remote state (S3 + DynamoDB)

Pick names that are globally unique (S3 bucket must be unique):

- state bucket: `incidentfox-tfstate-<your-unique-suffix>`
- lock table: `incidentfox-tflock`

## 2) Create AWS infra (ECR + VPC + EKS + IRSA + RDS)

Use the `pilot` env (remote state enabled) and create VPC/EKS/RDS for a self-contained pilot:

```bash
python scripts/incidentfoxctl.py \
  --env pilot \
  --aws-region us-east-1 \
  --state-bucket incidentfox-tfstate-REPLACE_ME \
  --lock-table incidentfox-tflock \
  --create-vpc \
  --create-eks \
  --create-rds \
  --install-controllers
```

Outputs to copy/inspect:

```bash
cd infra/terraform/envs/pilot
terraform output
```

## 3) Build + push images to ECR

Terraform creates ECR repos (by default in the `pilot` env). Get repo URLs:

```bash
cd infra/terraform/envs/pilot
terraform output -json | jq '.ecr_repository_urls.value'
```

Build/tag/push each service image with tag `pilot` (example flow):

```bash
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com
```

Then:

- `docker build -t <repo-url>:pilot -f config_service/Dockerfile . && docker push <repo-url>:pilot`
- `docker build -t <repo-url>:pilot -f orchestrator/Dockerfile . && docker push <repo-url>:pilot`
- `docker build -t <repo-url>:pilot -f ai_pipeline/Dockerfile . && docker push <repo-url>:pilot`
- `docker build -t <repo-url>:pilot -f agent/Dockerfile . && docker push <repo-url>:pilot`
- `docker build -t <repo-url>:pilot -f web_ui/Dockerfile . && docker push <repo-url>:pilot`

## 4) Secrets (AWS Secrets Manager + ESO)

Terraform creates these pilot secrets automatically (see `infra/terraform/envs/pilot/main.tf`):

- `incidentfox/pilot/database_url`
- `incidentfox/pilot/config_service_admin_token`
- `incidentfox/pilot/config_service_token_pepper`
- `incidentfox/pilot/config_service_impersonation_jwt_secret`
- `incidentfox/pilot/openai_api_key`

The only required manual step is to set a real value for **OpenAI**:

- Update `incidentfox/pilot/openai_api_key` in Secrets Manager to the real key.

Optional (if you want to overwrite any of the auto-generated secrets), you can seed/rotate them idempotently:

```bash
python scripts/seed_aws_secrets.py --region us-east-1 --from-stdin <<'JSON'
{
  "incidentfox/pilot/database_url": "postgresql+psycopg://USER:PASSWORD@HOST:5432/incidentfox",
  "incidentfox/pilot/config_service_admin_token": "REPLACE_ME",
  "incidentfox/pilot/config_service_token_pepper": "REPLACE_ME",
  "incidentfox/pilot/config_service_impersonation_jwt_secret": "REPLACE_ME",
  "incidentfox/pilot/openai_api_key": "REPLACE_ME"
}
JSON
```

## 5) Deploy IncidentFox via Helm

Update `charts/incidentfox/values.pilot.yaml`:
- set `externalSecrets.awsRegion`
- set service images to your ECR repo URLs (tag `pilot`)

Then:

```bash
helm upgrade --install incidentfox charts/incidentfox \
  -n incidentfox --create-namespace \
  -f charts/incidentfox/values.pilot.yaml
```

## 6) Smoke tests (happy path)

- `kubectl -n incidentfox get pods`
- `kubectl -n incidentfox logs deploy/incidentfox-config-service`
- `kubectl -n incidentfox logs deploy/incidentfox-orchestrator`
- `kubectl -n incidentfox get ingress`

Then:
- web_ui: login with `ADMIN_TOKEN` (pilot uses token auth)
- provision a team via web_ui admin page
- run an agent via web_ui “Run Agent”

## Cleanup

```bash
cd infra/terraform/envs/pilot
terraform destroy -auto-approve
```



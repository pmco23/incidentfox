# AI Agent System V2

Production-ready multi-agent AI system for infrastructure automation and troubleshooting.

## Features

- 🤖 **Multi-Agent Architecture**: Planner orchestrates expert agents (K8s, AWS, Coding, Metrics)
- ⚡ **Production-Grade**: Structured logging, metrics, retries, timeouts, error handling
- ☁️ **AWS Native**: ECS Fargate deployment, SSM Parameter Store config, CloudWatch
- 📊 **Observability**: Prometheus metrics, OpenTelemetry tracing, correlation IDs
- 🔧 **Configurable**: Environment vars, YAML, or AWS config service
- 🧪 **Well-Tested**: Comprehensive unit and integration tests

## Quick Start

### Local Development

```bash
# Install dependencies
poetry install

# Set required env vars
export OPENAI_API_KEY=your-key

# Run tests
poetry run pytest -v

# Run locally (CLI mode for testing)
poetry run python -m ai_agent
```

### Docker

```bash
# Build
docker build -t ai-agent .

# Run
docker run --env-file .env ai-agent
```

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-your-key

# IncidentFox Config Service Integration
USE_CONFIG_SERVICE=true
CONFIG_BASE_URL=https://config.incidentfox.com
INCIDENTFOX_TEAM_TOKEN=tokid.toksecret

# AWS
AWS_REGION=us-east-1
AWS_CONFIG_SERVICE_ENABLED=false  # SSM parameters (optional)
AWS_CONFIG_PARAMETER_PREFIX=/ai-agent/production/

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Metrics
METRICS_ENABLED=true
METRICS_CLOUDWATCH_ENABLED=true
```

**Note**: See `INCIDENTFOX_INTEGRATION.md` for detailed config service integration documentation.

### AWS SSM Parameters

Store configuration in SSM Parameter Store:

```bash
aws ssm put-parameter \
  --name /ai-agent/production/example-config \
  --value "your-value" \
  --type String
```

## Architecture

```
User Request
     ↓
Planner Agent (creates execution plan)
     ↓
┌─────────────────────────────────┐
│  Expert Agents (execute tasks)  │
│  - K8s Agent                     │
│  - AWS Agent                     │
│  - Coding Agent                  │
│  - Metrics Agent                 │
└─────────────────────────────────┘
     ↓
Tools (K8s API, AWS API, etc.)
     ↓
Results Aggregated & Returned
```

## Agents

### Planner Agent
Orchestrates complex tasks by:
- Analyzing requests
- Creating execution plans
- Routing to expert agents
- Managing dependencies

### K8s Agent
Kubernetes troubleshooting:
- Pod debugging
- Log analysis
- Resource inspection
- Event correlation

### AWS Agent
AWS resource management:
- EC2, Lambda, RDS debugging
- CloudWatch log analysis
- Resource status checks

### Coding Agent
Code analysis and fixes:
- Bug identification
- Code optimization
- Refactoring suggestions

## Deployment to AWS

### Prerequisites

- AWS CLI configured with `playground` profile
- Terraform installed
- Docker installed
- OpenAI API key

### Deploy Infrastructure

```bash
cd infra/terraform

# Initialize Terraform
terraform init

# Review plan
terraform plan \
  -var="openai_api_key=$OPENAI_API_KEY" \
  -var="team_token=$INCIDENTFOX_TEAM_TOKEN" \
  -var="aws_profile=playground"

# Apply
terraform apply \
  -var="openai_api_key=$OPENAI_API_KEY" \
  -var="team_token=$INCIDENTFOX_TEAM_TOKEN" \
  -var="aws_profile=playground"
```

This creates:
- ✅ ECS Fargate cluster and service
- ✅ Secrets in AWS Secrets Manager (encrypted)
- ✅ IAM roles with least privilege
- ✅ CloudWatch logs and metrics
- ✅ Security groups and VPC config
- ✅ ECR repository

### Build and Push Image

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 --profile playground | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t ai-agent .
docker tag ai-agent:latest <ecr-repo-url>:latest
docker push <ecr-repo-url>:latest
```

### Update ECS Service

```bash
aws ecs update-service \
  --cluster ai-agent-production \
  --service ai-agent \
  --force-new-deployment \
  --profile playground
```

## Monitoring

### CloudWatch Logs

```bash
aws logs tail /ecs/ai-agent-production --follow --profile playground
```

### Metrics

- **Prometheus**: http://localhost:9090/metrics
- **CloudWatch**: AIAgent namespace

Key metrics:
- `agent_requests_total` - Agent execution count
- `agent_duration_seconds` - Agent execution time
- `tool_calls_total` - Tool usage
- `errors_total` - Error tracking

### Tracing

OpenTelemetry traces with correlation IDs for request tracking.

## Development

### Project Structure

```
v2/
├── src/ai_agent/
│   ├── core/           # Framework (config, logging, metrics, runner)
│   ├── agents/         # Agent implementations
│   ├── tools/          # Tool implementations
│   └── integrations/   # External integrations
├── tests/              # Test suite
├── infra/terraform/    # AWS infrastructure
└── pyproject.toml      # Dependencies
```

### Running Tests

```bash
# All tests
poetry run pytest -v

# Unit tests only
poetry run pytest tests/unit/ -v

# With coverage
poetry run pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Linting
poetry run ruff check src/ tests/

# Type checking
poetry run mypy src/

# Format code
poetry run black src/ tests/
```

## CI/CD

GitHub Actions pipeline:
1. **Test** - Run tests and linters
2. **Build** - Build and push Docker image to ECR
3. **Deploy** - Update ECS service

## IncidentFox Config Service Integration

The system integrates with the IncidentFox Config Service for multi-tenant configuration:

### Features
- **Team-specific settings**: Each team gets their own config
- **Feature flags**: Enable/disable features per team
- **Agent customization**: Custom prompts and tools per team
- **Vault integration**: Secure secret management
- **Config inheritance**: Org-level defaults with team overrides

### Setup

```bash
# Set config service credentials
export USE_CONFIG_SERVICE=true
export CONFIG_BASE_URL=https://config.incidentfox.com
export INCIDENTFOX_TEAM_TOKEN=your-team-token

# Initialize vault for secrets
export VAULT_INCIDENTFOX_PROD_OPENAI=sk-your-key
export VAULT_INCIDENTFOX_PROD_SLACK_BOT=xoxb-your-token
```

### Usage

```python
from ai_agent.core.config import get_config
from ai_agent.core.vault import resolve_vault_path

# Get config with team settings
config = get_config()

if config.team_config:
    # Access team-specific settings
    slack_channel = config.team_config.slack_channel
    mcp_servers = config.team_config.mcp_servers
    
    # Check feature flags
    if config.team_config.is_feature_enabled("enable_auto_mitigation"):
        # Feature is enabled for this team
        pass
    
    # Resolve vault secrets
    if config.team_config.tokens_vault_path:
        openai_key = resolve_vault_path(
            config.team_config.tokens_vault_path.openai_token
        )
```

**Full documentation**: See `INCIDENTFOX_INTEGRATION.md`

## Troubleshooting

### Agent Not Starting

Check logs:
```bash
aws logs tail /ecs/ai-agent-production --follow --profile playground
```

Common issues:
- Missing OpenAI API key
- VPC/security group misconfiguration
- Insufficient IAM permissions

### High Memory Usage

Adjust Fargate task size in `terraform/variables.tf`:
```hcl
variable "memory" {
  default = 4096  # Increase from 2048
}
```

### Connection to Config Service Failed

Verify:
- Security groups allow traffic
- Config service endpoint is correct
- VPC routing is configured

## Performance Tuning

### Agent Timeout

Adjust in config:
```bash
export AGENT_TIMEOUT=600  # 10 minutes
```

### Concurrent Agents

```bash
export MAX_CONCURRENT_AGENTS=20
```

### OpenAI Settings

```bash
export OPENAI_MODEL=gpt-4-turbo
export OPENAI_TEMPERATURE=0.5
export OPENAI_MAX_TOKENS=8000
```

## Security

- API keys stored in AWS Secrets Manager
- Non-root Docker user
- VPC isolation
- IAM role-based permissions
- Encrypted ECR images

## License

Proprietary

## Support

For issues, contact your team lead or create a GitHub issue.


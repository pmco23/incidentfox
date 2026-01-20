# Security Group for ECS Tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "${local.app_name}-ecs-tasks-${var.environment}"
  description = "Security group for AI Agent ECS tasks"
  vpc_id      = local.vpc_id

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Health check"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  ingress {
    description = "Prometheus metrics"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }
}

data "aws_vpc" "selected" {
  id = local.vpc_id
}

# Secrets Manager for OpenAI API Key
resource "aws_secretsmanager_secret" "openai_key" {
  name                    = "${local.app_name}-openai-key-${var.environment}"
  description             = "OpenAI API key for AI Agent"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "openai_key" {
  secret_id = aws_secretsmanager_secret.openai_key.id
  secret_string = jsonencode({
    api_key = var.openai_api_key
  })
}

# Secrets Manager for Team Token
resource "aws_secretsmanager_secret" "team_token" {
  name                    = "${local.app_name}-team-token-${var.environment}"
  description             = "IncidentFox team authentication token"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "team_token" {
  secret_id = aws_secretsmanager_secret.team_token.id
  secret_string = jsonencode({
    token = var.team_token
  })
}

# Note: All secrets are injected directly as env vars by ECS
# No need for vault-style resolution - keep it simple!

# SSM Parameters for Configuration
resource "aws_ssm_parameter" "config_example" {
  name        = "/ai-agent/${var.environment}/example-config"
  description = "Example configuration parameter"
  type        = "String"
  value       = "example-value"

  tags = {
    Description = "Example parameter - add more as needed"
  }
}


# Security Group for ECS Tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "${local.app_name}-ecs-tasks-${var.environment}"
  description = "Security group for RAPTOR KB ECS tasks"
  vpc_id      = local.vpc_id

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description     = "Allow traffic from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "Allow traffic from VPC (for health checks)"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  tags = {
    Name = "${local.app_name}-ecs-sg"
  }
}

# Use existing OpenAI API Key from Secrets Manager
# The key is shared with the AI Agent service
data "aws_secretsmanager_secret" "openai_key" {
  arn = var.openai_secret_arn
}


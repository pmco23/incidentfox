# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${local.app_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "app" {
  family                   = local.app_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name  = local.app_name
      image = "${aws_ecr_repository.app.repository_url}:arm64"

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "AWS_CONFIG_SERVICE_ENABLED"
          value = "true"
        },
        {
          name  = "AWS_CONFIG_PARAMETER_PREFIX"
          value = "/ai-agent/${var.environment}/"
        },
        {
          name  = "LOG_LEVEL"
          value = var.environment == "production" ? "INFO" : "DEBUG"
        },
        {
          name  = "LOG_FORMAT"
          value = "json"
        },
        {
          name  = "METRICS_ENABLED"
          value = tostring(var.enable_metrics)
        },
        {
          name  = "METRICS_CLOUDWATCH_ENABLED"
          value = "true"
        },
        {
          name  = "USE_CONFIG_SERVICE"
          value = "true"
        },
        {
          name  = "CONFIG_BASE_URL"
          value = "http://internal-incidentfox-config-serv-internal-2010257803.us-west-2.elb.amazonaws.com"
        }
      ]

      secrets = [
        {
          name      = "OPENAI_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.openai_key.arn}:api_key::"
        },
        {
          name      = "INCIDENTFOX_TEAM_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.team_token.arn}:token::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        },
        {
          containerPort = 9090
          protocol      = "tcp"
          # Prometheus metrics
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}

# ECS Service
resource "aws_ecs_service" "app" {
  name            = local.app_name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.private.ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  enable_execute_command = true
}

# ECR Repository
resource "aws_ecr_repository" "app" {
  name                 = local.app_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}


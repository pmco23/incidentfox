# ECS Cluster (separate from agent cluster for isolation)
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
      image = "${aws_ecr_repository.app.repository_url}:latest"

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
          name  = "RAPTOR_TREES_DIR"
          value = "/app/trees"
        },
        {
          name  = "RAPTOR_DEFAULT_TREE"
          value = var.default_tree
        },
        {
          name  = "PORT"
          value = "8000"
        },
        {
          name  = "LOG_LEVEL"
          value = var.environment == "production" ? "INFO" : "DEBUG"
        },
        {
          name  = "TREES_S3_BUCKET"
          value = aws_s3_bucket.trees.id
        },
        {
          name  = "TREES_S3_PREFIX"
          value = "trees/"
        }
      ]

      secrets = [
        {
          name      = "OPENAI_API_KEY"
          valueFrom = "${data.aws_secretsmanager_secret.openai_key.arn}:api_key::"
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
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 120  # Tree loading takes time
      }
    }
  ])
}

# ECS Service with ALB
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

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = local.app_name
    container_port   = 8000
  }

  enable_execute_command = true

  depends_on = [aws_lb_listener.http]
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
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}


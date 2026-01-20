# Internal Application Load Balancer
resource "aws_lb" "internal" {
  name               = "${local.app_name}-internal"
  internal           = true  # Internal only - not exposed to internet
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.private.ids

  enable_deletion_protection = var.environment == "production"

  tags = {
    Name = "${local.app_name}-internal-alb"
  }
}

# ALB Security Group
resource "aws_security_group" "alb" {
  name        = "${local.app_name}-alb-${var.environment}"
  description = "Security group for RAPTOR KB internal ALB"
  vpc_id      = local.vpc_id

  ingress {
    description = "HTTP from VPC"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.app_name}-alb-sg"
  }
}

# Target Group
resource "aws_lb_target_group" "app" {
  name        = "${local.app_name}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = local.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }

  tags = {
    Name = "${local.app_name}-target-group"
  }
}

# HTTP Listener
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.internal.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}


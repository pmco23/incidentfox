terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

data "aws_iam_openid_connect_provider" "this" {
  arn = var.oidc_provider_arn
}

locals {
  oidc_subject_prefix = "system:serviceaccount"
}

#
# AWS Load Balancer Controller IRSA
#
resource "aws_iam_role" "alb_controller" {
  name = "${var.name_prefix}-alb-controller"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = { Federated = var.oidc_provider_arn },
        Action = "sts:AssumeRoleWithWebIdentity",
        Condition = {
          StringEquals = {
            "${replace(data.aws_iam_openid_connect_provider.this.url, "https://", "")}:sub" = "${local.oidc_subject_prefix}:${var.alb_namespace}:${var.alb_service_account_name}"
          }
        }
      }
    ]
  })
  tags = var.tags
}

# NOTE: In enterprise deployments you may want to scope this policy down further.
resource "aws_iam_policy" "alb_controller" {
  name   = "${var.name_prefix}-alb-controller"
  policy = file("${path.module}/policies/alb-controller.json")
}

resource "aws_iam_role_policy_attachment" "alb_attach" {
  role       = aws_iam_role.alb_controller.name
  policy_arn = aws_iam_policy.alb_controller.arn
}

#
# External Secrets Operator IRSA (AWS Secrets Manager)
#
resource "aws_iam_role" "external_secrets" {
  name = "${var.name_prefix}-external-secrets"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = { Federated = var.oidc_provider_arn },
        Action = "sts:AssumeRoleWithWebIdentity",
        Condition = {
          StringEquals = {
            "${replace(data.aws_iam_openid_connect_provider.this.url, "https://", "")}:sub" = "${local.oidc_subject_prefix}:${var.eso_namespace}:${var.eso_service_account_name}"
          }
        }
      }
    ]
  })
  tags = var.tags
}

resource "aws_iam_policy" "external_secrets" {
  name = "${var.name_prefix}-external-secrets"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecrets"
        ],
        Resource = var.secrets_manager_arns
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eso_attach" {
  role       = aws_iam_role.external_secrets.name
  policy_arn = aws_iam_policy.external_secrets.arn
}



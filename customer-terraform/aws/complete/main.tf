# ===================================================================
# IncidentFox AWS Infrastructure - Complete Stack
# ===================================================================
# This Terraform configuration creates all required AWS infrastructure:
# - VPC with public/private subnets
# - EKS Kubernetes cluster
# - RDS PostgreSQL database
# - IAM roles for AWS Load Balancer Controller
# - IAM roles for External Secrets Operator
#
# Prerequisites:
# - AWS CLI configured with appropriate credentials
# - Terraform >= 1.5.0
# ===================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Optional: Configure remote state backend
  # backend "s3" {
  #   bucket         = "incidentfox-terraform-state"
  #   key            = "incidentfox/terraform.tfstate"
  #   region         = "us-west-2"
  #   dynamodb_table = "incidentfox-terraform-lock"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      ManagedBy   = "Terraform"
      Application = "IncidentFox"
      Environment = var.environment
      Customer    = var.customer_name
    }
  }
}

# ===================================================================
# VPC Module
# ===================================================================
module "vpc" {
  source = "../../../infra/terraform/modules/vpc"

  name               = "${var.customer_name}-incidentfox"
  cidr_block         = var.vpc_cidr
  availability_zones = var.availability_zones

  tags = {
    Environment = var.environment
  }
}

# ===================================================================
# EKS Cluster Module
# ===================================================================
module "eks" {
  source = "../../../infra/terraform/modules/eks"

  name                = "${var.customer_name}-incidentfox"
  kubernetes_version  = var.kubernetes_version
  vpc_id              = module.vpc.vpc_id
  subnet_ids          = module.vpc.private_subnet_ids

  node_groups = {
    main = {
      desired_size   = var.eks_node_desired_count
      min_size       = var.eks_node_min_count
      max_size       = var.eks_node_max_count
      instance_types = var.eks_node_instance_types
    }
  }

  tags = {
    Environment = var.environment
  }
}

# ===================================================================
# RDS PostgreSQL Database Module
# ===================================================================
module "rds" {
  source = "../../../infra/terraform/modules/rds"

  name                       = "${var.customer_name}-incidentfox-db"
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_subnet_ids
  allowed_security_group_id  = module.eks.cluster_security_group_id

  engine_version         = var.rds_engine_version
  instance_class         = var.rds_instance_class
  allocated_storage_gb   = var.rds_allocated_storage_gb
  backup_retention_days  = var.rds_backup_retention_days
  deletion_protection    = var.rds_deletion_protection

  db_name     = "incidentfox"
  db_username = "incidentfox"
  db_password = var.rds_password  # Store securely! Use AWS Secrets Manager in production

  tags = {
    Environment = var.environment
  }
}

# ===================================================================
# IAM IRSA for AWS Load Balancer Controller
# ===================================================================
module "alb_controller_irsa" {
  source = "../../../infra/terraform/modules/iam_irsa"

  name                = "incidentfox-alb-controller"
  cluster_name        = module.eks.cluster_name
  cluster_oidc_issuer = module.eks.cluster_oidc_issuer_url
  namespace           = "kube-system"
  service_account     = "aws-load-balancer-controller"

  policy_arns = [
    "arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess"
  ]
}

# ===================================================================
# IAM IRSA for External Secrets Operator (Optional)
# ===================================================================
module "external_secrets_irsa" {
  count  = var.enable_external_secrets ? 1 : 0
  source = "../../../infra/terraform/modules/iam_irsa"

  name                = "incidentfox-external-secrets"
  cluster_name        = module.eks.cluster_name
  cluster_oidc_issuer = module.eks.cluster_oidc_issuer_url
  namespace           = "external-secrets"
  service_account     = "external-secrets"

  policy_arns = [
    "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
  ]
}

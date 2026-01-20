# ===================================================================
# IncidentFox AWS Infrastructure - Minimal Stack (RDS Only)
# ===================================================================
# This Terraform configuration creates ONLY the PostgreSQL database.
# Use this if you already have:
# - ✅ Existing EKS or Kubernetes cluster
# - ✅ VPC with private subnets
# - ✅ Ingress controller installed
#
# This will create:
# - RDS PostgreSQL database
# - Security group allowing access from your EKS cluster
# ===================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
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
# Data Sources - Reference your existing infrastructure
# ===================================================================

data "aws_vpc" "existing" {
  id = var.existing_vpc_id
}

data "aws_subnets" "database" {
  filter {
    name   = "vpc-id"
    values = [var.existing_vpc_id]
  }

  filter {
    name   = "tag:Name"
    values = var.database_subnet_tags
  }
}

# ===================================================================
# RDS PostgreSQL Database Module
# ===================================================================
module "rds" {
  source = "../../../infra/terraform/modules/rds"

  name                       = "${var.customer_name}-incidentfox-db"
  vpc_id                     = var.existing_vpc_id
  subnet_ids                 = data.aws_subnets.database.ids
  allowed_security_group_id  = var.eks_cluster_security_group_id

  engine_version         = var.rds_engine_version
  instance_class         = var.rds_instance_class
  allocated_storage_gb   = var.rds_allocated_storage_gb
  backup_retention_days  = var.rds_backup_retention_days
  deletion_protection    = var.rds_deletion_protection

  db_name     = "incidentfox"
  db_username = "incidentfox"
  db_password = var.rds_password

  tags = {
    Environment = var.environment
  }
}

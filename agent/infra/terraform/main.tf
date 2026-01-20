terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # backend "s3" {
  #   # Configure this based on your setup
  #   # bucket = "your-terraform-state-bucket"
  #   # key    = "ai-agent/terraform.tfstate"
  #   # region = "us-west-2"
  # }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = "ai-agent"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}

data "aws_vpcs" "existing" {
  filter {
    name   = "isDefault"
    values = ["false"]
  }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  filter {
    name   = "tag:Name"
    values = ["*private*"]
  }
}

# Locals
locals {
  app_name = "ai-agent"
  vpc_id   = var.vpc_id != "" ? var.vpc_id : tolist(data.aws_vpcs.existing.ids)[0]
}


terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # backend "s3" {
  #   bucket  = "incidentfox-terraform-state"
  #   key     = "knowledge-base/terraform.tfstate"
  #   region  = "us-west-2"
  #   profile = "playground"
  # }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = "raptor-kb"
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

data "aws_vpc" "selected" {
  id = local.vpc_id
}

# Locals
locals {
  app_name = "raptor-kb"
  vpc_id   = var.vpc_id != "" ? var.vpc_id : tolist(data.aws_vpcs.existing.ids)[0]
}

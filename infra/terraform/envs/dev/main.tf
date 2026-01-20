terraform {
  required_version = ">= 1.5.0"

  # NOTE: configure remote state here after state-bootstrap.
  # backend "s3" {
  #   bucket         = "REPLACE_ME"
  #   key            = "incidentfox/dev/terraform.tfstate"
  #   region         = "us-west-2"
  #   dynamodb_table = "REPLACE_ME"
  #   encrypt        = true
  # }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

locals {
  tags = merge(var.tags, { Environment = var.environment })
}

# Optional: create ECR repos (dev/pilot helper).
module "ecr" {
  count  = var.create_ecr ? 1 : 0
  source = "../../modules/ecr"

  name_prefix   = "incidentfox-${var.environment}"
  repositories  = var.ecr_repositories
  force_delete  = var.ecr_force_delete
  tags          = local.tags
}

# Optional: create a VPC (dev/pilot helper). Enterprises can BYO VPC/subnets instead.
module "vpc" {
  count  = var.create_vpc ? 1 : 0
  source = "../../modules/vpc"

  name               = "incidentfox-${var.environment}"
  cidr               = var.vpc_cidr
  azs                = var.vpc_azs
  public_subnets     = var.vpc_public_subnets
  private_subnets    = var.vpc_private_subnets
  single_nat_gateway = var.vpc_single_nat_gateway
  tags               = local.tags
}

locals {
  effective_vpc_id             = var.create_vpc ? module.vpc[0].vpc_id : var.vpc_id
  effective_private_subnet_ids = var.create_vpc ? module.vpc[0].private_subnet_ids : var.private_subnet_ids
}

# Optional: create an EKS cluster
module "eks" {
  count  = var.create_eks ? 1 : 0
  source = "../../modules/eks"

  cluster_name        = var.cluster_name
  cluster_version     = var.cluster_version
  cluster_endpoint_public_access       = var.cluster_endpoint_public_access
  cluster_endpoint_private_access      = var.cluster_endpoint_private_access
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs
  vpc_id              = local.effective_vpc_id
  private_subnet_ids  = local.effective_private_subnet_ids
  node_instance_types = var.node_instance_types
  node_ami_type       = var.node_ami_type
  node_min_size       = var.node_min_size
  node_max_size       = var.node_max_size
  node_desired_size   = var.node_desired_size
  tags                = local.tags
}

locals {
  oidc_provider_arn = var.create_eks ? module.eks[0].cluster_oidc_provider_arn : var.eks_oidc_provider_arn
  effective_node_sg = var.create_eks ? module.eks[0].node_security_group_id : var.eks_node_security_group_id
}

# IAM/IRSA for controllers
module "iam_irsa" {
  source            = "../../modules/iam_irsa"
  name_prefix       = "incidentfox-${var.environment}"
  oidc_provider_arn = local.oidc_provider_arn
  secrets_manager_arns = var.eso_allowed_secret_arns
  tags              = local.tags
}

# Optional: create RDS
module "rds" {
  count  = var.create_rds ? 1 : 0
  source = "../../modules/rds"

  name                     = "incidentfox-${var.environment}"
  vpc_id                    = local.effective_vpc_id
  subnet_ids                = local.effective_private_subnet_ids
  allowed_security_group_id = local.effective_node_sg
  db_name                   = var.db_name
  db_username               = var.db_username
  db_password               = var.db_password
  tags                      = local.tags
}



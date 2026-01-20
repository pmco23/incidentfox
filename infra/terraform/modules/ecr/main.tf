terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  repo_names = [for r in var.repositories : "${var.name_prefix}-${r}"]
}

resource "aws_ecr_repository" "repos" {
  for_each = toset(local.repo_names)

  name         = each.value
  force_delete = var.force_delete

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}



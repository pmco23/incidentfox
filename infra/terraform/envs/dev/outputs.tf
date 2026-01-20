output "alb_controller_role_arn" {
  value = module.iam_irsa.alb_controller_role_arn
}

output "external_secrets_role_arn" {
  value = module.iam_irsa.external_secrets_role_arn
}

output "ecr_repository_urls" {
  value = try(module.ecr[0].repository_urls, null)
}

output "eks_cluster_name" {
  value = try(module.eks[0].cluster_name, null)
}

output "eks_node_security_group_id" {
  value = try(module.eks[0].node_security_group_id, null)
}

output "vpc_id" {
  value = try(module.vpc[0].vpc_id, null)
}

output "private_subnet_ids" {
  value = try(module.vpc[0].private_subnet_ids, null)
}

output "rds_endpoint" {
  value = try(module.rds[0].db_endpoint, null)
}



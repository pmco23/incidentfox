# ===================================================================
# Outputs - Important values you'll need for Helm installation
# ===================================================================

output "vpc_id" {
  description = "VPC ID where resources are deployed"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "EKS cluster name - use with 'aws eks update-kubeconfig'"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_configure_kubectl_command" {
  description = "Command to configure kubectl to connect to this cluster"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "database_endpoint" {
  description = "RDS PostgreSQL endpoint (hostname:port)"
  value       = module.rds.endpoint
}

output "database_connection_string" {
  description = "PostgreSQL connection string for IncidentFox"
  value       = "postgresql://incidentfox:${var.rds_password}@${module.rds.endpoint}/incidentfox"
  sensitive   = true
}

output "database_connection_string_k8s_secret" {
  description = "Kubernetes secret creation command for database URL"
  value       = <<-EOT
    kubectl create secret generic incidentfox-database-url \
      --from-literal=DATABASE_URL="postgresql://incidentfox:${var.rds_password}@${module.rds.endpoint}/incidentfox" \
      -n incidentfox
  EOT
  sensitive   = true
}

output "alb_controller_role_arn" {
  description = "IAM role ARN for AWS Load Balancer Controller"
  value       = module.alb_controller_irsa.role_arn
}

output "external_secrets_role_arn" {
  description = "IAM role ARN for External Secrets Operator"
  value       = var.enable_external_secrets ? module.external_secrets_irsa[0].role_arn : null
}

# ===================================================================
# Next Steps Summary
# ===================================================================

output "next_steps" {
  description = "What to do after Terraform completes"
  value       = <<-EOT

    ===================================================================
    ✅ AWS Infrastructure Created Successfully!
    ===================================================================

    Next Steps:

    1. Configure kubectl to access your EKS cluster:
       ${module.eks.cluster_configure_command}

    2. Install AWS Load Balancer Controller:
       helm repo add eks https://aws.github.io/eks-charts
       helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
         -n kube-system \
         --set clusterName=${module.eks.cluster_name} \
         --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=${module.alb_controller_irsa.role_arn}

    3. Create database secret in Kubernetes:
       kubectl create namespace incidentfox
       kubectl create secret generic incidentfox-database-url \
         --from-literal=DATABASE_URL="postgresql://incidentfox:****@${module.rds.endpoint}/incidentfox" \
         -n incidentfox

    4. Continue with Helm installation:
       See: ../../../docs/customer/installation-guide.md

    ===================================================================

  EOT
}

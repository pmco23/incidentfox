output "database_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = module.rds.endpoint
}

output "database_connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://incidentfox:${var.rds_password}@${module.rds.endpoint}/incidentfox"
  sensitive   = true
}

output "database_secret_create_command" {
  description = "Kubernetes secret creation command"
  value       = <<-EOT
    kubectl create secret generic incidentfox-database-url \
      --from-literal=DATABASE_URL="postgresql://incidentfox:${var.rds_password}@${module.rds.endpoint}/incidentfox" \
      -n incidentfox
  EOT
  sensitive   = true
}

output "next_steps" {
  value       = <<-EOT
    ✅ RDS PostgreSQL database created!

    Next: Create database secret in Kubernetes and continue with Helm installation.
    See: ../../../docs/CUSTOMER_INSTALLATION_GUIDE.md
  EOT
}

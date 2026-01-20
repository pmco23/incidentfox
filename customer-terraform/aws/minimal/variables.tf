# Required Variables

variable "customer_name" {
  description = "Your organization name (lowercase, alphanumeric only)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "rds_password" {
  description = "PostgreSQL master password (min 16 characters)"
  type        = string
  sensitive   = true
}

# Existing Infrastructure

variable "existing_vpc_id" {
  description = "ID of your existing VPC"
  type        = string
}

variable "database_subnet_tags" {
  description = "Subnet tag patterns for database (e.g., ['*private*', '*database*'])"
  type        = list(string)
  default     = ["*private*"]
}

variable "eks_cluster_security_group_id" {
  description = "Security group ID of your EKS cluster nodes"
  type        = string
}

# RDS Configuration

variable "rds_engine_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"
}

variable "rds_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t3.large"
}

variable "rds_allocated_storage_gb" {
  description = "Initial storage size in GB"
  type        = number
  default     = 100
}

variable "rds_backup_retention_days" {
  description = "Backup retention days"
  type        = number
  default     = 7
}

variable "rds_deletion_protection" {
  description = "Prevent accidental deletion"
  type        = bool
  default     = true
}

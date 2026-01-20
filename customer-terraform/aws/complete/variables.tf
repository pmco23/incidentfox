# ===================================================================
# Required Variables
# ===================================================================

variable "customer_name" {
  description = "Your organization name (lowercase, alphanumeric only). Example: acme-corp"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.customer_name))
    error_message = "Customer name must be lowercase alphanumeric with hyphens only."
  }
}

variable "aws_region" {
  description = "AWS region to deploy resources. Example: us-west-2"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name. Example: production, staging, dev"
  type        = string
  default     = "production"
}

variable "rds_password" {
  description = "PostgreSQL master password (min 16 characters, store securely!)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.rds_password) >= 16
    error_message = "RDS password must be at least 16 characters long."
  }
}

# ===================================================================
# Network Configuration
# ===================================================================

variable "vpc_cidr" {
  description = "CIDR block for VPC. Must not overlap with existing networks."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for high availability (minimum 2 required)"
  type        = list(string)
  default     = ["us-west-2a", "us-west-2b", "us-west-2c"]
}

# ===================================================================
# EKS Configuration
# ===================================================================

variable "kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.29"
}

variable "eks_node_desired_count" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 3
}

variable "eks_node_min_count" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 3
}

variable "eks_node_max_count" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 6
}

variable "eks_node_instance_types" {
  description = "EC2 instance types for worker nodes"
  type        = list(string)
  default     = ["t3.xlarge"]  # 4 vCPU, 16GB RAM
}

# ===================================================================
# RDS Configuration
# ===================================================================

variable "rds_engine_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"
}

variable "rds_instance_class" {
  description = "RDS instance type. See: https://aws.amazon.com/rds/instance-types/"
  type        = string
  default     = "db.t3.large"  # 2 vCPU, 8GB RAM
}

variable "rds_allocated_storage_gb" {
  description = "Initial database storage size in GB"
  type        = number
  default     = 100
}

variable "rds_backup_retention_days" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 7
}

variable "rds_deletion_protection" {
  description = "Prevent accidental database deletion"
  type        = bool
  default     = true
}

# ===================================================================
# Optional Features
# ===================================================================

variable "enable_external_secrets" {
  description = "Enable External Secrets Operator for AWS Secrets Manager integration"
  type        = bool
  default     = true
}

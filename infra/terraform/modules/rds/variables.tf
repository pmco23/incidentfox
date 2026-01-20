variable "name" {
  type        = string
  description = "RDS identifier base name"
}

variable "vpc_id" {
  type        = string
  description = "VPC id"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet ids for DB subnet group"
}

variable "allowed_security_group_id" {
  type        = string
  description = "Security group allowed to connect to Postgres (typically EKS node/cluster SG)"
}

variable "engine_version" {
  type    = string
  default = "16.3"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "allocated_storage_gb" {
  type    = number
  default = 50
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "db_name" {
  type    = string
  default = "incidentfox"
}

variable "db_username" {
  type    = string
  default = "incidentfox"
}

variable "db_password" {
  type        = string
  description = "DB password (pass via TF_VAR_db_password or secret manager tooling)"
  sensitive   = true
}

variable "tags" {
  type    = map(string)
  default = {}
}



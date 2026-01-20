variable "name_prefix" {
  type        = string
  description = "Prefix for IAM role/policy names"
}

variable "oidc_provider_arn" {
  type        = string
  description = "EKS OIDC provider ARN"
}

variable "alb_namespace" {
  type    = string
  default = "kube-system"
}

variable "alb_service_account_name" {
  type    = string
  default = "aws-load-balancer-controller"
}

variable "eso_namespace" {
  type    = string
  default = "incidentfox-system"
}

variable "eso_service_account_name" {
  type    = string
  default = "external-secrets"
}

variable "secrets_manager_arns" {
  type        = list(string)
  description = "List of Secrets Manager ARNs ESO is allowed to read"
}

variable "tags" {
  type    = map(string)
  default = {}
}



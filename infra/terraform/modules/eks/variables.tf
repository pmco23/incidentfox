variable "cluster_name" {
  type        = string
  description = "EKS cluster name"
}

variable "cluster_version" {
  type        = string
  description = "EKS version"
  default     = "1.30"
}

variable "cluster_endpoint_public_access" {
  type        = bool
  description = "Whether the EKS cluster endpoint is publicly accessible"
  default     = false
}

variable "cluster_endpoint_private_access" {
  type        = bool
  description = "Whether the EKS cluster endpoint is privately accessible within the VPC"
  default     = true
}

variable "cluster_endpoint_public_access_cidrs" {
  type        = list(string)
  description = "Allowed CIDRs for public EKS endpoint access"
  default     = []
}

variable "vpc_id" {
  type        = string
  description = "VPC id"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet ids for the cluster"
}

variable "node_instance_types" {
  type        = list(string)
  default     = ["m7g.large"]
  description = "Managed node group instance types"
}

variable "node_ami_type" {
  type        = string
  description = "EKS managed node group AMI type (must match instance architecture)"
  # Default aligns with Graviton instances (m7g.*).
  default     = "AL2023_ARM_64_STANDARD"
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 4
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to AWS resources"
}



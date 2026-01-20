variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "aws_profile" {
  description = "AWS profile to use"
  type        = string
  default     = "playground"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "vpc_id" {
  description = "VPC ID to deploy into (leave empty to use existing VPC)"
  type        = string
  default     = ""
}

variable "cpu" {
  description = "CPU units for Fargate task"
  type        = number
  default     = 2048  # 2 vCPU - needed for loading large tree
}

variable "memory" {
  description = "Memory for Fargate task"
  type        = number
  default     = 8192  # 8 GB - tree is 1.5GB, needs headroom for embeddings
}

variable "desired_count" {
  description = "Desired number of tasks"
  type        = number
  default     = 1  # Start with 1, scale as needed
}

variable "openai_secret_arn" {
  description = "ARN of existing OpenAI API key secret in Secrets Manager"
  type        = string
  default     = "arn:aws:secretsmanager:us-west-2:103002841599:secret:ai-agent-openai-key-production-ioanzg"
}

variable "default_tree" {
  description = "Default RAPTOR tree to load"
  type        = string
  default     = "mega_ultra_v2"
}

variable "enable_metrics" {
  description = "Enable CloudWatch metrics"
  type        = bool
  default     = true
}

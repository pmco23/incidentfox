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
  default     = 1024  # 1 vCPU
}

variable "memory" {
  description = "Memory for Fargate task"
  type        = number
  default     = 2048  # 2 GB
}

variable "desired_count" {
  description = "Desired number of tasks"
  type        = number
  default     = 2
}

variable "openai_api_key" {
  description = "OpenAI API key (will be stored in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "team_token" {
  description = "IncidentFox team token (will be stored in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "slack_bot_token" {
  description = "Slack bot token (optional, will be stored in Secrets Manager)"
  type        = string
  sensitive   = true
  default     = ""
}


variable "enable_metrics" {
  description = "Enable CloudWatch metrics"
  type        = bool
  default     = true
}


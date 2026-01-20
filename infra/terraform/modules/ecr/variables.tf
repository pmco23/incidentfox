variable "name_prefix" {
  type        = string
  description = "Prefix for ECR repository names"
}

variable "repositories" {
  type        = list(string)
  description = "Repository suffix names (will be prefixed by name_prefix)"
  default     = ["config-service", "orchestrator", "ai-pipeline-api", "agent", "web-ui"]
}

variable "force_delete" {
  type        = bool
  description = "Allow deleting repos even if images exist (useful for pilot stacks)"
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to AWS resources"
  default     = {}
}



variable "aws_region" {
  type        = string
  description = "AWS region"
}

variable "aws_profile" {
  type        = string
  description = "AWS profile"
  default     = ""
}

variable "state_bucket_name" {
  type        = string
  description = "S3 bucket name for terraform state"
}

variable "lock_table_name" {
  type        = string
  description = "DynamoDB table name for terraform state locking"
}



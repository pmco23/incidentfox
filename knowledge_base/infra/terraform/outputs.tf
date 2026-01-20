output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.app.name
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.app.repository_url
}

output "alb_dns_name" {
  description = "DNS name of the internal ALB (use this as RAPTOR_API_URL)"
  value       = aws_lb.internal.dns_name
}

output "alb_url" {
  description = "Full URL of the internal ALB"
  value       = "http://${aws_lb.internal.dns_name}"
}

output "s3_trees_bucket" {
  description = "S3 bucket for RAPTOR tree files"
  value       = aws_s3_bucket.trees.id
}

output "log_group_name" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.app.name
}

output "task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task.arn
}

output "web_ui_env_var" {
  description = "Environment variable to add to web_ui .env.local"
  value       = "RAPTOR_API_URL=http://${aws_lb.internal.dns_name}"
}

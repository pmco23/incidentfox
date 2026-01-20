output "repository_urls" {
  value = { for name, r in aws_ecr_repository.repos : name => r.repository_url }
}



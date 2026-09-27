output "repository_url" {
  description = "Repository URL for publishing and deploying images."
  value       = aws_ecr_repository.this.repository_url
}

output "repository_arn" {
  description = "Repository ARN for scoped delivery policies."
  value       = aws_ecr_repository.this.arn
}

output "service_name" {
  description = "Service name. Pass this to the deploy lane."
  value       = aws_ecs_service.this.name
}

output "task_family" {
  description = "Task definition family the deploy lane revises."
  value       = aws_ecs_task_definition.this.family
}

output "container_name" {
  description = "Container the deploy lane targets."
  value       = var.container_name
}

output "security_group_id" {
  description = "Task security group, to allow as a source on dependencies."
  value       = aws_security_group.task.id
}

output "task_role_arn" {
  description = "Runtime identity ARN."
  value       = aws_iam_role.task.arn
}

output "task_role_name" {
  description = "Runtime identity name, for attaching policies outside this module."
  value       = aws_iam_role.task.name
}

output "log_group_name" {
  description = "CloudWatch log group receiving container output."
  value       = aws_cloudwatch_log_group.this.name
}

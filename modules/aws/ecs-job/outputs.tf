output "task_family" {
  description = "Task definition family. Pass this to the task lane."
  value       = aws_ecs_task_definition.this.family
}

output "task_definition_arn" {
  description = "Current task definition revision ARN."
  value       = aws_ecs_task_definition.this.arn
}

output "container_name" {
  description = "Container the task lane overrides and reads logs from."
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

output "log_group_name" {
  description = "CloudWatch log group receiving job output."
  value       = aws_cloudwatch_log_group.this.name
}

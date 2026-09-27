output "application_id" {
  description = "Pass this to the data lane as emr_application_id."
  value       = aws_emrserverless_application.this.id
}

output "job_role_arn" {
  description = "Pass this to the data lane as emr_job_role_arn."
  value       = aws_iam_role.job.arn
}

output "job_role_name" {
  description = "Role name, for attaching further policies outside this module."
  value       = aws_iam_role.job.name
}

output "log_group_name" {
  description = "Log group receiving driver and executor output."
  value       = aws_cloudwatch_log_group.this.name
}

output "security_group_id" {
  description = "Job security group, or null when jobs run outside the VPC."
  value       = try(aws_security_group.job[0].id, null)
}

output "role_arn" {
  description = "Role ARN to set as AWS_ROLE_ARN in the calling repository."
  value       = aws_iam_role.this.arn
}

output "role_name" {
  description = "Role name, for attaching further policies outside this module."
  value       = aws_iam_role.this.name
}

output "allowed_subjects" {
  description = "OIDC subject patterns allowed to assume the role."
  value       = local.subjects
}

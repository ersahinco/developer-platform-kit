output "endpoint" {
  description = "Host and port for clients."
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "Hostname only."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "Listening port."
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "Initial database name."
  value       = aws_db_instance.this.db_name
}

output "master_secret_arn" {
  description = "RDS-managed master credential secret ARN. Inject this, never a literal password."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "client_security_group_id" {
  description = "Attach this to any workload that may reach the database."
  value       = aws_security_group.client.id
}

output "database_security_group_id" {
  description = "Security group attached to the instance itself."
  value       = aws_security_group.database.id
}

output "kms_key_arn" {
  description = "Key encrypting database storage and Performance Insights."
  value       = var.kms_key_arn == null ? aws_kms_key.this[0].arn : var.kms_key_arn
}

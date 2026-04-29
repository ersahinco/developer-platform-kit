output "alb_dns_name" {
  description = "Public DNS of the ALB. Useful for inspection, but the intended endpoint is api_fqdn."
  value       = aws_lb.this.dns_name
}

output "api_fqdn" {
  description = "Public DNS name for the single API endpoint in Route 53."
  value       = local.api_fqdn
}

output "alb_url" {
  description = "HTTPS base URL for the API."
  value       = "https://${local.api_fqdn}"
}

output "acm_certificate_arn" {
  description = "ACM certificate ARN attached to the HTTPS listener."
  value       = aws_acm_certificate_validation.api.certificate_arn
}

output "ecr_app_repository_url" {
  description = "ECR URL for the app image."
  value       = module.ecr_app.repository_url
}

output "ecr_worker_repository_url" {
  description = "ECR URL for the worker image."
  value       = module.ecr_worker.repository_url
}

output "ecr_liquibase_repository_url" {
  description = "ECR URL for the Liquibase migrations image."
  value       = module.ecr_liquibase.repository_url
}

output "ecr_data_export_job_repository_url" {
  description = "ECR URL for the data export job image."
  value       = module.ecr_data_export_job.repository_url
}

output "worker_task_definition_arn" {
  description = "Worker task definition ARN. Pass to `aws ecs run-task` to trigger a backfill."
  value       = aws_ecs_task_definition.worker.arn
}

output "data_export_job_task_definition_arn" {
  description = "Data export job task definition ARN used by EventBridge Scheduler."
  value       = aws_ecs_task_definition.data_export_job.arn
}

output "data_export_schedule_name" {
  description = "EventBridge Scheduler name for the recurring data export job."
  value       = aws_scheduler_schedule.data_export_job.name
}

output "liquibase_task_definition_arn" {
  description = "Liquibase task definition ARN for one-off schema migration tasks."
  value       = aws_ecs_task_definition.liquibase.arn
}

output "rds_endpoint" {
  description = "RDS instance endpoint (host:port). Not publicly accessible — accessed via pgbouncer sidecar."
  value       = module.rds.db_instance_endpoint
}

output "db_secret_arn" {
  description = "Secrets Manager ARN for the RDS credentials managed by RDS."
  value       = module.rds.db_instance_master_user_secret_arn
}

output "data_hub_bucket_name" {
  description = "S3 bucket for data export raw, curated, and manifest prefixes."
  value       = aws_s3_bucket.data_hub.bucket
}

output "data_hub_prefixes" {
  description = "S3 prefixes reserved for data hub raw, curated, and manifest objects."
  value       = local.data_hub_prefixes
}

output "ecs_cluster_name" {
  description = "ECS cluster name for the single stack."
  value       = module.ecs.cluster_name
}

output "app_service_name" {
  description = "ECS service name for the long-running app."
  value       = module.ecs.services["app"].name
}

output "app_task_exec_role_arn" {
  description = "Task execution role ARN shared by the app and one-off support tasks."
  value       = aws_iam_role.task_exec.arn
}

output "app_task_role_arn" {
  description = "Task role ARN for app runtime permissions."
  value       = module.ecs.services["app"].tasks_iam_role_arn
}

output "private_subnet_ids" {
  description = "Private subnet IDs used by the ECS service and one-off tasks."
  value       = module.vpc.private_subnets
}

output "app_security_group_id" {
  description = "App security group ID used by the ECS service and one-off tasks."
  value       = aws_security_group.app.id
}

output "github_actions_role_arn" {
  description = "IAM role ARN assumed by GitHub Actions through OIDC."
  value       = aws_iam_role.github_actions.arn
}

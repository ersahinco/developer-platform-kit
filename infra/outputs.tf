output "alb_dns_name" {
  description = "Public DNS of the ALB — use as BASE_URL in smoke tests."
  value       = aws_lb.this.dns_name
}

output "ecr_app_repository_url" {
  description = "ECR URL for the app image. Push target in CI: $ECR_APP_URL:sha-$GITHUB_SHA"
  value       = module.ecr_app.repository_url
}

output "ecr_worker_repository_url" {
  description = "ECR URL for the worker image."
  value       = module.ecr_worker.repository_url
}

output "ecr_liquibase_repository_url" {
  description = "ECR URL for the Liquibase migrations image. Push target in CI: $ECR_LIQUIBASE_URL:sha-$GITHUB_SHA"
  value       = module.ecr_liquibase.repository_url
}

output "worker_task_definition_arn" {
  description = "Worker task definition ARN. Pass to `aws ecs run-task` to trigger a backfill."
  value       = aws_ecs_task_definition.worker.arn
}

output "liquibase_task_definition_arn" {
  description = "Liquibase task definition ARN. Pass to `aws ecs run-task` for schema migrations. Set as LIQUIBASE_TASK_DEF_ARN in GitHub."
  value       = aws_ecs_task_definition.liquibase.arn
}

output "rds_endpoint" {
  description = "RDS instance endpoint (host:port). Not publicly accessible — accessed via pgbouncer sidecar."
  value       = module.rds.db_instance_endpoint
}

output "db_secret_arn" {
  description = "Secrets Manager ARN for RDS credentials (managed by RDS). Set as DB_SECRET_ARN in GitHub."
  value       = module.rds.db_instance_master_user_secret_arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name. Set as ECS_CLUSTER in GitHub."
  value       = module.ecs.cluster_name
}

output "app_service_name" {
  description = "ECS app service name. Set as APP_SERVICE_NAME in GitHub."
  value       = module.ecs.services["app"].name
}

output "app_task_exec_role_arn" {
  description = "Task execution role ARN. Set as TASK_EXEC_ROLE_ARN in GitHub."
  value       = aws_iam_role.task_exec.arn
}

output "app_task_role_arn" {
  description = "Task role ARN (app runtime permissions). Set as TASK_ROLE_ARN in GitHub."
  value       = module.ecs.services["app"].tasks_iam_role_arn
}

output "private_subnet_ids" {
  description = "Private subnet IDs for migrate tasks. Set as PRIVATE_SUBNET_IDS in GitHub."
  value       = module.vpc.private_subnets
}

output "app_security_group_id" {
  description = "App security group ID for run-task. Set as APP_SG_ID in GitHub."
  value       = aws_security_group.app.id
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC. Set as AWS_ROLE_ARN in GitHub."
  value       = aws_iam_role.github_actions.arn
}

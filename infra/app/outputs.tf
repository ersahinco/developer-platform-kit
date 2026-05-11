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

output "edge_waf_web_acl_arn" {
  description = "WAFv2 Web ACL ARN associated with the public API ALB."
  value       = aws_wafv2_web_acl.edge.arn
}

output "app_unhealthy_targets_alarm_name" {
  description = "CloudWatch alarm for unhealthy ALB targets behind the app service."
  value       = aws_cloudwatch_metric_alarm.app_unhealthy_targets.alarm_name
}

output "app_symptom_cloudwatch_alarms_enabled" {
  description = "Whether app target 5xx and latency CloudWatch alarms are enabled."
  value       = var.enable_app_symptom_cloudwatch_alarms
}

output "app_target_5xx_alarm_name" {
  description = "CloudWatch alarm for target-generated 5xx responses behind the ALB."
  value       = var.enable_app_symptom_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.app_target_5xx[0].alarm_name : null
}

output "app_target_latency_alarm_name" {
  description = "CloudWatch alarm for elevated app target response time behind the ALB."
  value       = var.enable_app_symptom_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.app_target_latency[0].alarm_name : null
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

output "ecr_order_event_consumer_repository_url" {
  description = "ECR URL for the order event consumer image."
  value       = module.ecr_order_event_consumer.repository_url
}

output "ecr_firelens_repository_url" {
  description = "ECR URL for the FireLens log router image."
  value       = module.ecr_firelens.repository_url
}

output "worker_task_definition_arn" {
  description = "Worker task definition ARN. Pass to `aws ecs run-task` to trigger a backfill."
  value       = aws_ecs_task_definition.worker.arn
}

output "data_export_job_task_definition_arn" {
  description = "Data export job task definition ARN used by EventBridge Scheduler."
  value       = aws_ecs_task_definition.data_export_job.arn
}

output "order_event_consumer_service_name" {
  description = "ECS service name for the order event relay/consumer."
  value       = aws_ecs_service.order_event_consumer.name
}

output "data_export_schedule_name" {
  description = "EventBridge Scheduler name for the recurring data export job."
  value       = aws_scheduler_schedule.data_export_job.name
}

output "data_export_scheduler_target_errors_alarm_name" {
  description = "CloudWatch alarm for EventBridge Scheduler data export target delivery failures."
  value       = aws_cloudwatch_metric_alarm.data_export_scheduler_target_errors.alarm_name
}

output "data_export_success_metric_namespace" {
  description = "CloudWatch namespace for the data export success metric."
  value       = "${local.name}/DataExport"
}

output "data_export_success_metric_name" {
  description = "CloudWatch metric name emitted when a data export succeeds."
  value       = "SuccessCount"
}

output "data_export_success_cloudwatch_alarm_enabled" {
  description = "Whether the data export success CloudWatch metric filter and freshness alarm are enabled."
  value       = var.enable_data_export_success_cloudwatch_alarm
}

output "data_export_success_missing_alarm_name" {
  description = "CloudWatch alarm for missing scheduled data export successes."
  value       = var.enable_data_export_success_cloudwatch_alarm ? aws_cloudwatch_metric_alarm.data_export_success_missing[0].alarm_name : null
}

output "liquibase_task_definition_arn" {
  description = "Liquibase task definition ARN for one-off schema migration tasks."
  value       = aws_ecs_task_definition.liquibase.arn
}

output "rds_endpoint" {
  description = "RDS instance endpoint (host:port). Not publicly accessible — accessed via pgbouncer sidecar."
  value       = module.rds.db_instance_endpoint
}

output "rds_instance_identifier" {
  description = "RDS instance identifier used by CloudWatch metrics and AWS CLI inspection."
  value       = module.rds.db_instance_identifier
}

output "db_secret_arn" {
  description = "Secrets Manager ARN for the RDS credentials managed by RDS."
  value       = module.rds.db_instance_master_user_secret_arn
}

output "rds_cpu_high_alarm_name" {
  description = "CloudWatch alarm for high RDS CPU utilization."
  value       = aws_cloudwatch_metric_alarm.rds_cpu_high.alarm_name
}

output "rds_free_storage_low_alarm_name" {
  description = "CloudWatch alarm for low RDS free storage."
  value       = aws_cloudwatch_metric_alarm.rds_free_storage_low.alarm_name
}

output "rds_connections_high_alarm_name" {
  description = "CloudWatch alarm for elevated RDS database connections."
  value       = aws_cloudwatch_metric_alarm.rds_connections_high.alarm_name
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
  description = "ECS cluster name for the app stack."
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
  value       = aws_iam_role.app_task.arn
}

output "order_events_queue_url" {
  description = "Dapr subscriber SQS FIFO queue URL for order.created.v1 events."
  value       = aws_sqs_queue.order_events.url
}

output "order_events_topic_arn" {
  description = "SNS FIFO topic ARN used by Dapr order event pub/sub."
  value       = aws_sns_topic.order_events.arn
}

output "order_events_dlq_name" {
  description = "SQS DLQ name for order event messages that exceed the receive retry policy."
  value       = aws_sqs_queue.order_events_dlq.name
}

output "order_events_dlq_visible_alarm_name" {
  description = "CloudWatch alarm for visible messages in the order events DLQ."
  value       = aws_cloudwatch_metric_alarm.order_events_dlq_visible.alarm_name
}

output "private_subnet_ids" {
  description = "Private subnet IDs used by the ECS service and one-off tasks."
  value       = local.platform.private_subnet_ids
}

output "app_security_group_id" {
  description = "App security group ID used by the ECS service and one-off tasks."
  value       = aws_security_group.app.id
}

output "github_actions_role_arn" {
  description = "IAM role ARN assumed by GitHub Actions through OIDC."
  value       = local.github_actions_role_arn
}

output "observability_stack_enabled" {
  description = "Whether the optional ECS Grafana/Loki/Prometheus stack is enabled."
  value       = var.enable_observability_stack
}

output "observability_bucket_name" {
  description = "S3 bucket for optional observability config and Loki storage."
  value       = var.enable_observability_stack ? aws_s3_bucket.observability[0].bucket : null
}

output "observability_private_namespace" {
  description = "Private Cloud Map namespace used by the optional observability stack."
  value       = var.enable_observability_stack ? aws_service_discovery_private_dns_namespace.observability[0].name : null
}

output "observability_grafana_service_name" {
  description = "ECS service name for optional Grafana."
  value       = var.enable_observability_stack ? aws_ecs_service.grafana[0].name : null
}

output "observability_loki_service_name" {
  description = "ECS service name for optional Loki."
  value       = var.enable_observability_stack ? aws_ecs_service.loki[0].name : null
}

output "observability_prometheus_service_name" {
  description = "ECS service name for optional Prometheus."
  value       = var.enable_observability_stack ? aws_ecs_service.prometheus[0].name : null
}

output "observability_tempo_service_name" {
  description = "ECS service name for optional Tempo."
  value       = var.enable_observability_stack ? aws_ecs_service.tempo[0].name : null
}

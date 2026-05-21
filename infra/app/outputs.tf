output "primary_edge_fqdn" {
  description = "Public DNS name for the primary edge workload in Route 53."
  value       = local.primary_edge_fqdn
}

output "primary_edge_unhealthy_targets_alarm_name" {
  description = "CloudWatch alarm for unhealthy ALB targets behind the primary edge workload."
  value       = aws_cloudwatch_metric_alarm.primary_edge_unhealthy_targets.alarm_name
}

output "primary_edge_symptom_cloudwatch_alarms_enabled" {
  description = "Whether primary edge target 5xx and latency CloudWatch alarms are enabled."
  value       = var.enable_primary_edge_symptom_cloudwatch_alarms
}

output "primary_edge_target_5xx_alarm_name" {
  description = "CloudWatch alarm for target-generated 5xx responses behind the primary edge workload."
  value       = var.enable_primary_edge_symptom_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.primary_edge_target_5xx[0].alarm_name : null
}

output "primary_edge_target_latency_alarm_name" {
  description = "CloudWatch alarm for elevated primary edge target response time behind the ALB."
  value       = var.enable_primary_edge_symptom_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.primary_edge_target_latency[0].alarm_name : null
}

output "primary_edge_service_name" {
  description = "ECS service name for the primary public edge workload."
  value       = aws_ecs_service.primary_edge.name
}

output "event_consumer_service_name" {
  description = "ECS service name for the event consumer workload."
  value       = aws_ecs_service.event_consumer.name
}

output "data_export_schedule_name" {
  description = "EventBridge Scheduler name for the recurring data export job."
  value       = aws_scheduler_schedule.data_export_job.name
}

output "data_export_scheduler_target_errors_alarm_name" {
  description = "CloudWatch alarm for EventBridge Scheduler data export target delivery failures."
  value       = aws_cloudwatch_metric_alarm.data_export_scheduler_target_errors.alarm_name
}

output "data_export_success_cloudwatch_alarm_enabled" {
  description = "Whether the data export success CloudWatch metric filter and freshness alarm are enabled."
  value       = var.enable_data_export_success_cloudwatch_alarm
}

output "data_export_success_missing_alarm_name" {
  description = "CloudWatch alarm for missing scheduled data export successes."
  value       = var.enable_data_export_success_cloudwatch_alarm ? aws_cloudwatch_metric_alarm.data_export_success_missing[0].alarm_name : null
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

output "ecs_cluster_name" {
  description = "ECS cluster name for the app stack."
  value       = module.ecs.cluster_name
}

output "async_eventing_queue_url" {
  description = "Dapr subscriber SQS FIFO queue URL for async event deliveries."
  value       = aws_sqs_queue.async_eventing.url
}

output "async_eventing_dlq_name" {
  description = "SQS DLQ name for async event messages that exceed the receive retry policy."
  value       = aws_sqs_queue.async_eventing_dlq.name
}

output "async_eventing_dlq_visible_alarm_name" {
  description = "CloudWatch alarm for visible messages in the async eventing DLQ."
  value       = aws_cloudwatch_metric_alarm.async_eventing_dlq_visible.alarm_name
}

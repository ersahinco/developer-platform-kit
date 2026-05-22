################################################################################
# State moves for platform-runtime internal renames
#
# These moves keep the platform cleanup in-place. Without them, Terraform would
# treat internal label renames as destroy/create operations and cross the app
# deploy ownership boundary with unnecessary cloud deletes.
################################################################################

moved {
  from = aws_iam_role.api_task
  to   = aws_iam_role.primary_edge_task
}

moved {
  from = aws_iam_policy.api_task
  to   = aws_iam_policy.primary_edge_task
}

moved {
  from = aws_iam_role_policy_attachment.api_task_internal
  to   = aws_iam_role_policy_attachment.primary_edge_task_internal
}

moved {
  from = aws_iam_role_policy.task_ssm_exec
  to   = aws_iam_role_policy.primary_edge_task_ssm_exec
}

moved {
  from = aws_cloudwatch_log_group.api
  to   = aws_cloudwatch_log_group.primary_edge
}

moved {
  from = aws_security_group.api
  to   = aws_security_group.primary_edge
}

moved {
  from = aws_lb_target_group.api
  to   = aws_lb_target_group.primary_edge
}

moved {
  from = aws_cloudwatch_metric_alarm.api_unhealthy_targets
  to   = aws_cloudwatch_metric_alarm.primary_edge_unhealthy_targets
}

moved {
  from = aws_cloudwatch_metric_alarm.api_target_5xx
  to   = aws_cloudwatch_metric_alarm.primary_edge_target_5xx[0]
}

moved {
  from = aws_cloudwatch_metric_alarm.api_target_latency
  to   = aws_cloudwatch_metric_alarm.primary_edge_target_latency[0]
}

moved {
  from = aws_acm_certificate.api
  to   = aws_acm_certificate.primary_edge
}

moved {
  from = aws_route53_record.api_cert_validation
  to   = aws_route53_record.primary_edge_cert_validation
}

moved {
  from = aws_acm_certificate_validation.api
  to   = aws_acm_certificate_validation.primary_edge
}

moved {
  from = aws_route53_record.api_alias
  to   = aws_route53_record.primary_edge_alias
}

moved {
  from = aws_ecs_task_definition.api
  to   = aws_ecs_task_definition.primary_edge
}

moved {
  from = aws_ecs_service.api
  to   = aws_ecs_service.primary_edge
}

moved {
  from = aws_iam_role.order_event_consumer
  to   = aws_iam_role.event_consumer
}

moved {
  from = aws_iam_role_policy.order_event_consumer_sqs
  to   = aws_iam_role_policy.event_consumer_sqs
}

moved {
  from = aws_ecs_task_definition.order_event_consumer
  to   = aws_ecs_task_definition.event_consumer
}

moved {
  from = aws_cloudwatch_log_group.order_event_consumer
  to   = aws_cloudwatch_log_group.event_consumer
}

moved {
  from = aws_ecs_service.order_event_consumer
  to   = aws_ecs_service.event_consumer
}

moved {
  from = module.ecr["order_event_consumer"]
  to   = module.ecr["event_consumer"]
}

moved {
  from = aws_kms_key.order_events_sns
  to   = aws_kms_key.async_eventing_sns
}

moved {
  from = aws_kms_alias.order_events_sns
  to   = aws_kms_alias.async_eventing_sns
}

moved {
  from = aws_sns_topic.order_events
  to   = aws_sns_topic.async_eventing
}

moved {
  from = aws_sqs_queue.order_events_dlq
  to   = aws_sqs_queue.async_eventing_dlq
}

moved {
  from = aws_sqs_queue.order_events
  to   = aws_sqs_queue.async_eventing
}

moved {
  from = aws_sqs_queue_policy.order_events
  to   = aws_sqs_queue_policy.async_eventing
}

moved {
  from = aws_sns_topic_subscription.order_events_consumer
  to   = aws_sns_topic_subscription.async_eventing_consumer
}

moved {
  from = aws_s3_object.order_events_dapr_component
  to   = aws_s3_object.async_eventing_dapr_component
}

moved {
  from = aws_s3_object.order_events_dapr_config
  to   = aws_s3_object.async_eventing_dapr_config
}

moved {
  from = aws_s3_object.order_events_dapr_resiliency
  to   = aws_s3_object.async_eventing_dapr_resiliency
}

moved {
  from = aws_cloudwatch_metric_alarm.order_events_dlq_visible
  to   = aws_cloudwatch_metric_alarm.async_eventing_dlq_visible
}

moved {
  from = aws_ecs_task_definition.backfill_worker
  to   = aws_ecs_task_definition.support_job["backfill_worker"]
}

moved {
  from = aws_ecs_task_definition.data_export_job
  to   = aws_ecs_task_definition.support_job["data_export_job"]
}

moved {
  from = aws_cloudwatch_log_group.backfill_worker
  to   = aws_cloudwatch_log_group.support_job["backfill_worker"]
}

moved {
  from = aws_cloudwatch_log_group.data_export_job
  to   = aws_cloudwatch_log_group.support_job["data_export_job"]
}

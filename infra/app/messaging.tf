################################################################################
# Messaging
#
# SQS is the current AWS implementation for app-owned messaging. Keep queues,
# workload IAM, and queue alarms together because they are one delivery
# capability even when the transport changes later.
################################################################################

resource "aws_sqs_queue" "order_events_dlq" {
  name                      = "${local.name}-order-events-dlq.fifo"
  fifo_queue                = true
  sqs_managed_sse_enabled   = true
  message_retention_seconds = 1209600

  tags = local.tags
}

resource "aws_sqs_queue" "order_events" {
  name                       = "${local.name}-order-events.fifo"
  fifo_queue                 = true
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.order_events_dlq.arn
    maxReceiveCount     = 5
  })

  tags = local.tags
}

data "aws_iam_policy_document" "app_order_events_sqs" {
  statement {
    sid = "PublishOrderEvents"
    actions = [
      "sqs:GetQueueAttributes",
      "sqs:SendMessage",
    ]
    resources = [aws_sqs_queue.order_events.arn]
  }
}

resource "aws_iam_role_policy" "app_order_events_sqs" {
  name   = "publish-order-events"
  role   = module.ecs.services["app"].tasks_iam_role_name
  policy = data.aws_iam_policy_document.app_order_events_sqs.json
}

resource "aws_cloudwatch_metric_alarm" "order_events_dlq_visible" {
  alarm_name          = "${local.name}-order-events-dlq-visible"
  alarm_description   = "Order event messages are visible in the DLQ. Runbook: docs/runbooks/order-event-queue-failure.md"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  threshold           = 0
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  treat_missing_data  = "notBreaching"
  unit                = "Count"

  dimensions = {
    QueueName = aws_sqs_queue.order_events_dlq.name
  }

  tags = local.tags
}

################################################################################
# Messaging
#
# Dapr is the app transport boundary for order events. Terraform still owns the
# AWS broker assets so the platform can keep IAM, DLQs, and alarms explicit.
################################################################################

locals {
  order_events_topic_name          = "${local.name}-order-created-v1.fifo"
  order_event_consumer_queue_name  = "${local.name}-order-event-consumer.fifo"
  order_events_runtime_bucket_name = "${local.name}-runtime-config-${local.account_id}"
  order_events_dapr_config_prefix  = "config/dapr/order-events"
}

resource "aws_sns_topic" "order_events" {
  name                        = local.order_events_topic_name
  fifo_topic                  = true
  content_based_deduplication = true

  tags = local.tags
}

resource "aws_sqs_queue" "order_events_dlq" {
  name                      = "${local.name}-order-events-dlq.fifo"
  fifo_queue                = true
  sqs_managed_sse_enabled   = true
  message_retention_seconds = 1209600

  tags = local.tags
}

resource "aws_sqs_queue" "order_events" {
  name                       = local.order_event_consumer_queue_name
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

data "aws_iam_policy_document" "order_events_queue" {
  statement {
    sid       = "AllowSnsOrderEvents"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.order_events.arn]

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.order_events.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "order_events" {
  queue_url = aws_sqs_queue.order_events.url
  policy    = data.aws_iam_policy_document.order_events_queue.json
}

resource "aws_sns_topic_subscription" "order_events_consumer" {
  topic_arn            = aws_sns_topic.order_events.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.order_events.arn
  raw_message_delivery = true

  depends_on = [aws_sqs_queue_policy.order_events]
}

################################################################################
# Runtime config for Dapr sidecars on Fargate
################################################################################

resource "aws_s3_bucket" "runtime_config" {
  #checkov:skip=CKV_AWS_18:Access logs add cost/noise for a bucket containing only generated runtime config.
  #checkov:skip=CKV_AWS_144:Cross-region replication is recovery overhead outside this lean sandbox.
  #checkov:skip=CKV_AWS_145:S3-managed AES256 encryption is sufficient for non-secret Dapr component config.
  #checkov:skip=CKV2_AWS_62:No event consumer exists for runtime config bucket notifications.
  bucket = local.order_events_runtime_bucket_name

  tags = merge(local.tags, {
    Purpose = "runtime-config"
  })
}

resource "aws_s3_bucket_public_access_block" "runtime_config" {
  bucket = aws_s3_bucket.runtime_config.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "runtime_config" {
  bucket = aws_s3_bucket.runtime_config.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "runtime_config" {
  bucket = aws_s3_bucket.runtime_config.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "runtime_config" {
  bucket = aws_s3_bucket.runtime_config.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "runtime_config" {
  bucket = aws_s3_bucket.runtime_config.id

  rule {
    id     = "expire-noncurrent-runtime-config-versions"
    status = "Enabled"

    filter {
      prefix = ""
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.runtime_config]
}

resource "aws_s3_object" "order_events_dapr_component" {
  bucket       = aws_s3_bucket.runtime_config.id
  key          = "${local.order_events_dapr_config_prefix}/components/order-events-pubsub.yaml"
  content_type = "text/yaml"
  content = templatefile("${path.module}/templates/dapr/order-events-pubsub.yaml.tftpl", {
    aws_region            = local.region
    dlq_name              = aws_sqs_queue.order_events_dlq.name
    subscriber_queue_name = aws_sqs_queue.order_events.name
  })
}

resource "aws_s3_object" "order_events_dapr_config" {
  bucket       = aws_s3_bucket.runtime_config.id
  key          = "${local.order_events_dapr_config_prefix}/config/config.yaml"
  content_type = "text/yaml"
  content      = templatefile("${path.module}/templates/dapr/config.yaml.tftpl", {})
}

resource "aws_s3_object" "order_events_dapr_resiliency" {
  bucket       = aws_s3_bucket.runtime_config.id
  key          = "${local.order_events_dapr_config_prefix}/components/resiliency.yaml"
  content_type = "text/yaml"
  content      = templatefile("${path.module}/templates/dapr/resiliency.yaml.tftpl", {})
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

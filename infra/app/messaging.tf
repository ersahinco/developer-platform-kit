################################################################################
# Messaging
#
# Dapr is the app transport boundary for async events. Terraform still owns the
# AWS broker assets so the platform can keep IAM, DLQs, and alarms explicit.
################################################################################

locals {
  primary_async_eventing_queue_name = "${local.name}-${local.primary_async_eventing_repository}.fifo"
  runtime_config_bucket_name        = "${local.name}-runtime-config-${local.account_id}"
  primary_async_eventing_dapr_config_prefix = (
    "config/dapr/${local.primary_async_eventing_repository}"
  )
}

resource "aws_sns_topic" "async_eventing" {
  name                        = local.primary_async_eventing_topic_name
  fifo_topic                  = true
  content_based_deduplication = true
  kms_master_key_id           = aws_kms_key.async_eventing_sns.arn

  tags = local.tags
}

resource "aws_sqs_queue" "async_eventing_dlq" {
  name                      = "${local.name}-async-events-dlq.fifo"
  fifo_queue                = true
  sqs_managed_sse_enabled   = true
  message_retention_seconds = 1209600

  tags = local.tags
}

resource "aws_sqs_queue" "async_eventing" {
  name                       = local.primary_async_eventing_queue_name
  fifo_queue                 = true
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.async_eventing_dlq.arn
    maxReceiveCount     = 5
  })

  tags = local.tags
}

data "aws_iam_policy_document" "async_eventing_queue" {
  statement {
    sid       = "AllowSnsAsyncEvents"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.async_eventing.arn]

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.async_eventing.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "async_eventing" {
  queue_url = aws_sqs_queue.async_eventing.url
  policy    = data.aws_iam_policy_document.async_eventing_queue.json
}

resource "aws_sns_topic_subscription" "async_eventing_consumer" {
  topic_arn            = aws_sns_topic.async_eventing.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.async_eventing.arn
  raw_message_delivery = true

  depends_on = [aws_sqs_queue_policy.async_eventing]
}

################################################################################
# Runtime config for Dapr sidecars on Fargate
################################################################################

resource "aws_s3_bucket" "runtime_config" {
  #checkov:skip=CKV_AWS_18:Access logs add cost/noise for a bucket containing only generated runtime config.
  #checkov:skip=CKV_AWS_144:Cross-region replication is recovery overhead outside this lean sandbox.
  #checkov:skip=CKV_AWS_145:S3-managed AES256 encryption is sufficient for non-secret Dapr component config.
  #checkov:skip=CKV2_AWS_62:No event consumer exists for runtime config bucket notifications.
  bucket        = local.runtime_config_bucket_name
  force_destroy = true

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

resource "aws_s3_object" "async_eventing_dapr_component" {
  bucket       = aws_s3_bucket.runtime_config.id
  key          = "${local.primary_async_eventing_dapr_config_prefix}/components/async-events-pubsub.yaml"
  content_type = "text/yaml"
  content = templatefile("${path.module}/templates/dapr/async-events-pubsub.yaml.tftpl", {
    aws_region            = local.region
    dlq_name              = aws_sqs_queue.async_eventing_dlq.name
    subscriber_queue_name = aws_sqs_queue.async_eventing.name
  })
}

resource "aws_s3_object" "async_eventing_dapr_config" {
  bucket       = aws_s3_bucket.runtime_config.id
  key          = "${local.primary_async_eventing_dapr_config_prefix}/config/config.yaml"
  content_type = "text/yaml"
  content      = templatefile("${path.module}/templates/dapr/config.yaml.tftpl", {})
}

resource "aws_s3_object" "async_eventing_dapr_resiliency" {
  bucket       = aws_s3_bucket.runtime_config.id
  key          = "${local.primary_async_eventing_dapr_config_prefix}/components/resiliency.yaml"
  content_type = "text/yaml"
  content      = templatefile("${path.module}/templates/dapr/resiliency.yaml.tftpl", {})
}

resource "aws_cloudwatch_metric_alarm" "async_eventing_dlq_visible" {
  alarm_name          = "${local.name}-async-events-dlq-visible"
  alarm_description   = "Async event messages are visible in the DLQ. Runbook: docs/runbooks/event-consumer-queue-failure.md"
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
    QueueName = aws_sqs_queue.async_eventing_dlq.name
  }

  tags = local.tags
}

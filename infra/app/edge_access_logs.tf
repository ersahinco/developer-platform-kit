################################################################################
# ALB access logs
#
# The edge access-log bucket is separated from the retired observability stack
# so ALB audit logs do not require self-hosting Grafana, Loki, Prometheus, and
# Tempo. The bucket name intentionally preserves the previous S3 bucket to avoid
# replacing or emptying deployed ALB log storage during the cutover.
################################################################################

locals {
  alb_access_logs_bucket_name = "${local.name}-observability-${local.account_id}"
}

moved {
  from = aws_s3_bucket.observability[0]
  to   = aws_s3_bucket.alb_access_logs
}

moved {
  from = aws_s3_bucket_public_access_block.observability[0]
  to   = aws_s3_bucket_public_access_block.alb_access_logs
}

moved {
  from = aws_s3_bucket_ownership_controls.observability[0]
  to   = aws_s3_bucket_ownership_controls.alb_access_logs
}

moved {
  from = aws_s3_bucket_policy.observability_alb_access_logs[0]
  to   = aws_s3_bucket_policy.alb_access_logs
}

moved {
  from = aws_s3_bucket_server_side_encryption_configuration.observability[0]
  to   = aws_s3_bucket_server_side_encryption_configuration.alb_access_logs
}

moved {
  from = aws_s3_bucket_versioning.observability[0]
  to   = aws_s3_bucket_versioning.alb_access_logs
}

moved {
  from = aws_s3_bucket_lifecycle_configuration.observability[0]
  to   = aws_s3_bucket_lifecycle_configuration.alb_access_logs
}

resource "aws_s3_bucket" "alb_access_logs" {
  #checkov:skip=CKV_AWS_18:This is the access-log destination bucket, so self-logging would recurse.
  #checkov:skip=CKV_AWS_144:Cross-region replication is production recovery overhead, not needed for this lean runtime.
  #checkov:skip=CKV_AWS_145:S3-managed AES256 encryption is sufficient here; KMS adds cost and key operations for access logs.
  #checkov:skip=CKV2_AWS_62:No event consumer exists for ALB access-log bucket notifications.
  bucket = local.alb_access_logs_bucket_name

  tags = merge(local.tags, {
    Purpose = "alb-access-logs"
  })
}

resource "aws_s3_bucket_public_access_block" "alb_access_logs" {
  bucket = aws_s3_bucket.alb_access_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "alb_access_logs" {
  bucket = aws_s3_bucket.alb_access_logs.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

data "aws_iam_policy_document" "alb_access_logs" {
  statement {
    sid = "AllowAlbAccessLogs"

    principals {
      type        = "Service"
      identifiers = ["logdelivery.elasticloadbalancing.amazonaws.com"]
    }

    actions = ["s3:PutObject"]

    resources = [
      "${aws_s3_bucket.alb_access_logs.arn}/alb-access-logs/AWSLogs/${local.account_id}/*",
    ]
  }
}

resource "aws_s3_bucket_policy" "alb_access_logs" {
  bucket = aws_s3_bucket.alb_access_logs.id
  policy = data.aws_iam_policy_document.alb_access_logs.json
}

resource "aws_s3_bucket_server_side_encryption_configuration" "alb_access_logs" {
  bucket = aws_s3_bucket.alb_access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "alb_access_logs" {
  bucket = aws_s3_bucket.alb_access_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_access_logs" {
  bucket = aws_s3_bucket.alb_access_logs.id

  rule {
    id     = "expire-noncurrent-access-log-versions"
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

  depends_on = [aws_s3_bucket_versioning.alb_access_logs]
}

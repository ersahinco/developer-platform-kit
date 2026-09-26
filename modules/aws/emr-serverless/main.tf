################################################################################
# EMR Serverless
#
# One Spark application plus the runtime role its jobs assume. Capacity is
# pre-initialised so a job does not wait for a cold start, and bounded so a
# runaway job cannot consume the account.
#
# The data lane publishes job code to S3 and calls start-job-run against this
# application. Nothing about a specific pipeline lives here.
################################################################################

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}

resource "aws_cloudwatch_log_group" "this" {
  # checkov:skip=CKV_AWS_338:Retention is a consumer cost/compliance choice; default 30 days, set log_retention_days to 365 for annual retention.
  # checkov:skip=CKV_AWS_158:CloudWatch encrypts at rest with service-managed keys; add a customer key when compliance requires its lifecycle ownership.

  name              = "/aws/emr-serverless/${var.name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

resource "aws_emrserverless_application" "this" {
  name          = var.name
  type          = "spark"
  release_label = var.release_label

  architecture = var.architecture

  maximum_capacity {
    cpu    = var.maximum_cpu
    memory = var.maximum_memory
  }

  auto_start_configuration {
    enabled = true
  }

  auto_stop_configuration {
    enabled              = true
    idle_timeout_minutes = var.idle_timeout_minutes
  }

  dynamic "network_configuration" {
    for_each = length(var.subnet_ids) == 0 ? [] : [1]
    content {
      subnet_ids         = var.subnet_ids
      security_group_ids = [aws_security_group.job[0].id]
    }
  }

  tags = var.tags
}

# Only needed when jobs reach VPC resources such as a database. A job that only
# reads and writes S3 needs no network configuration at all.
resource "aws_security_group" "job" {
  count = length(var.subnet_ids) == 0 ? 0 : 1

  name_prefix = "${var.name}-emr-"
  description = "Spark job network placement for ${var.name}"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_vpc_security_group_egress_rule" "job" {
  count = length(var.subnet_ids) == 0 ? 0 : 1

  security_group_id = aws_security_group.job[0].id
  description       = "Outbound to S3, Glue, and job dependencies"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

################################################################################
# Job runtime identity
################################################################################

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["emr-serverless.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "job" {
  name               = "${var.name}-job"
  description        = "Runtime identity for ${var.name} Spark jobs"
  assume_role_policy = data.aws_iam_policy_document.assume.json

  tags = var.tags
}

data "aws_iam_policy_document" "job" {
  statement {
    sid       = "ListDataBuckets"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [for bucket in var.data_bucket_names : "arn:${data.aws_partition.current.partition}:s3:::${bucket}"]
  }

  statement {
    sid     = "ReadWriteDataObjects"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [
      for bucket in var.data_bucket_names :
      "arn:${data.aws_partition.current.partition}:s3:::${bucket}/*"
    ]
  }

  statement {
    sid = "WriteJobLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }

  dynamic "statement" {
    for_each = var.glue_catalog_access ? [1] : []
    content {
      sid = "ReadGlueCatalog"
      actions = [
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetTable",
        "glue:GetTables",
        "glue:GetPartition",
        "glue:GetPartitions",
        "glue:CreateTable",
        "glue:UpdateTable",
        "glue:BatchCreatePartition",
        "glue:CreatePartition",
        "glue:UpdatePartition",
      ]
      resources = ["*"]
    }
  }
}

resource "aws_iam_role_policy" "job" {
  name   = "${var.name}-job"
  role   = aws_iam_role.job.id
  policy = data.aws_iam_policy_document.job.json
}

resource "aws_iam_role_policy" "job_extra" {
  for_each = var.additional_job_policy_json

  name   = each.key
  role   = aws_iam_role.job.id
  policy = each.value
}

################################################################################
# CloudWatch Logs encryption
################################################################################

data "aws_iam_policy_document" "cloudwatch_logs_kms" {
  #checkov:skip=CKV_AWS_109:KMS key policy needs an account-root administration path to avoid lockout; CloudWatch Logs use is constrained by encryption context below.
  statement {
    sid = "AllowAccountKeyAdministration"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid = "AllowCloudWatchLogsUse"

    principals {
      type        = "Service"
      identifiers = ["logs.${local.region}.amazonaws.com"]
    }

    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
      "kms:GenerateDataKeyWithoutPlaintext",
      "kms:ReEncryptFrom",
      "kms:ReEncryptTo",
      "kms:DescribeKey",
    ]

    resources = ["*"]

    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/${local.name}/*"]
    }
  }
}

resource "aws_kms_key" "cloudwatch_logs" {
  description         = "Encrypt CloudWatch log groups for ${local.name}"
  enable_key_rotation = true
  policy              = data.aws_iam_policy_document.cloudwatch_logs_kms.json

  tags = merge(local.tags, {
    Purpose = "cloudwatch-logs"
  })
}

resource "aws_kms_alias" "cloudwatch_logs" {
  name          = "alias/${local.name}/cloudwatch-logs"
  target_key_id = aws_kms_key.cloudwatch_logs.key_id
}

################################################################################
# Order event SNS encryption
################################################################################

data "aws_iam_policy_document" "order_events_sns_kms" {
  #checkov:skip=CKV_AWS_109:KMS key policy needs an account-root administration path to avoid lockout; SNS use is constrained by source account/topic below.
  statement {
    sid = "AllowAccountKeyAdministration"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid = "AllowSnsUseForOrderEvents"

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey",
      "kms:GenerateDataKeyWithoutPlaintext",
    ]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:sns:topicArn"
      values   = ["arn:aws:sns:${local.region}:${local.account_id}:${local.primary_async_eventing_topic_name}"]
    }
  }
}

resource "aws_kms_key" "order_events_sns" {
  description         = "Encrypt SNS order event topic for ${local.name}"
  enable_key_rotation = true
  policy              = data.aws_iam_policy_document.order_events_sns_kms.json

  tags = merge(local.tags, {
    Purpose = "order-events-sns"
  })
}

resource "aws_kms_alias" "order_events_sns" {
  name          = "alias/${local.name}/order-events-sns"
  target_key_id = aws_kms_key.order_events_sns.key_id
}

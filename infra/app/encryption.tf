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

################################################################################
# GitHub Actions identity
#
# One role per delivery lane, assumed through the GitHub OIDC provider. No
# long-lived access keys. Subjects are pinned to named environments and refs, so
# a fork or an arbitrary branch cannot assume the role.
#
# This module owns trust and Terraform state access. It deliberately does not
# ship a catalog of service permissions: attach the policies the lane actually
# needs through policy_arns or inline_policy_json, and review them in the repo
# that owns them.
################################################################################

data "aws_partition" "current" {}

locals {
  subjects = concat(
    [for env in var.environments : "repo:${var.github_repository}:environment:${env}"],
    [for ref in var.refs : "repo:${var.github_repository}:ref:${ref}"],
  )
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = var.oidc_thumbprints

  tags = var.tags
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type = "Federated"
      identifiers = [
        var.create_oidc_provider
        ? aws_iam_openid_connect_provider.github[0].arn
        : data.aws_iam_openid_connect_provider.github[0].arn
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.subjects
    }
  }
}

resource "aws_iam_role" "this" {
  name                 = var.name
  description          = "GitHub Actions delivery lane for ${var.github_repository}"
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  max_session_duration = var.max_session_duration

  tags = var.tags

  lifecycle {
    precondition {
      condition     = length(local.subjects) > 0
      error_message = "Set environments or refs. A role with no allowed subject can never be assumed."
    }
  }
}

data "aws_iam_policy_document" "state_access" {
  count = var.state_bucket == null ? 0 : 1

  statement {
    sid       = "TerraformStateBucket"
    actions   = ["s3:ListBucket"]
    resources = ["arn:${data.aws_partition.current.partition}:s3:::${var.state_bucket}"]
  }

  statement {
    sid     = "TerraformStateObjects"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [
      "arn:${data.aws_partition.current.partition}:s3:::${var.state_bucket}/${var.state_key_prefix}*"
    ]
  }
}

resource "aws_iam_policy" "state_access" {
  count = var.state_bucket == null ? 0 : 1

  name   = "${var.name}-state-access"
  policy = data.aws_iam_policy_document.state_access[0].json
  tags   = var.tags
}

resource "aws_iam_role_policy_attachment" "state_access" {
  count = var.state_bucket == null ? 0 : 1

  role       = aws_iam_role.this.name
  policy_arn = aws_iam_policy.state_access[0].arn
}

resource "aws_iam_role_policy_attachment" "managed" {
  for_each = var.policy_arns

  role       = aws_iam_role.this.name
  policy_arn = each.value
}

resource "aws_iam_role_policy" "inline" {
  for_each = var.inline_policy_json

  name   = each.key
  role   = aws_iam_role.this.id
  policy = each.value
}

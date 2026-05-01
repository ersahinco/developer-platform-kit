################################################################################
# GitHub Actions OIDC identity
#
# Platform owns the account-level trust relationship and CI role identity. App
# roots may attach app-scoped deploy policies to this role after platform exists.
################################################################################

locals {
  github_actions_oidc_subjects = [
    "repo:${var.github_repository}:environment:*",
    "repo:${var.github_repository}:ref:refs/heads/main",
    "repo:${var.github_repository}:ref:refs/pull/*/head",
  ]

  github_actions_state_bucket_name = "${local.name}-tfstate-${local.account_id}"
}

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "github_actions_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.github_actions_oidc_subjects
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${local.name}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "github_actions_state_access" {
  statement {
    sid = "TerraformState"
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:PutObject",
    ]
    resources = [
      "arn:aws:s3:::${local.github_actions_state_bucket_name}",
      "arn:aws:s3:::${local.github_actions_state_bucket_name}/*",
    ]
  }

  statement {
    sid = "TerraformStateLock"
    actions = [
      "dynamodb:DeleteItem",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
    ]
    resources = ["arn:aws:dynamodb:${local.region}:${local.account_id}:table/terraform-locks"]
  }
}

resource "aws_iam_policy" "github_actions_state_access" {
  name   = "${local.name}-github-actions-state-access"
  policy = data.aws_iam_policy_document.github_actions_state_access.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_state_access" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_state_access.arn
}

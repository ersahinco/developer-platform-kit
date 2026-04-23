################################################################################
# GitHub Actions OIDC federation
#
# Keep one deployment role for this repository. The trust relationship stays
# repo-scoped, while the attached managed policies are organized by operational
# concern so reviews can focus on one surface area at a time.
################################################################################

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

################################################################################
# Concern-scoped managed policies
#
# This phase keeps the single GitHub Actions role, but replaces the old mixed
# policy groupings with narrower review units. Effective access is intended to
# remain unchanged because each statement is carried over with the same actions,
# resources, and conditions.
################################################################################

resource "aws_iam_policy" "github_actions_state_access" {
  name   = "${local.name}-github-actions-state-access"
  policy = data.aws_iam_policy_document.github_actions_state_access.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_compute_deploy" {
  name   = "${local.name}-github-actions-compute-deploy"
  policy = data.aws_iam_policy_document.github_actions_compute_deploy.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_ecr" {
  name   = "${local.name}-github-actions-ecr"
  policy = data.aws_iam_policy_document.github_actions_ecr.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_networking" {
  name   = "${local.name}-github-actions-networking"
  policy = data.aws_iam_policy_document.github_actions_networking.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_edge_dns" {
  name   = "${local.name}-github-actions-edge-dns"
  policy = data.aws_iam_policy_document.github_actions_edge_dns.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_logs_secrets" {
  name   = "${local.name}-github-actions-logs-secrets"
  policy = data.aws_iam_policy_document.github_actions_logs_secrets.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_identity_kms" {
  name   = "${local.name}-github-actions-identity-kms"
  policy = data.aws_iam_policy_document.github_actions_identity_kms.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_managed" {
  for_each = {
    state_access   = aws_iam_policy.github_actions_state_access.arn
    compute_deploy = aws_iam_policy.github_actions_compute_deploy.arn
    ecr            = aws_iam_policy.github_actions_ecr.arn
    networking     = aws_iam_policy.github_actions_networking.arn
    edge_dns       = aws_iam_policy.github_actions_edge_dns.arn
    logs_secrets   = aws_iam_policy.github_actions_logs_secrets.arn
    identity_kms   = aws_iam_policy.github_actions_identity_kms.arn
  }

  role       = aws_iam_role.github_actions.name
  policy_arn = each.value
}

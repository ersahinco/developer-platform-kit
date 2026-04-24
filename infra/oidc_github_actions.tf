################################################################################
# GitHub Actions OIDC federation
#
# Keep one deployment role for this repository. The trust relationship stays
# repo-scoped, while the attached managed policies are organized by operational
# concern so reviews can focus on one surface area at a time.
#
# Base GitHub Actions OIDC is intentionally kept in this single file so one
# conceptual area does not get spread across too many files. Optional policy
# extensions remain isolated in `oidc_optional_features.tf`.
################################################################################

locals {
  github_actions_oidc_subjects = [
    "repo:ersahinco/aws-sdlc-containers:environment:*",
    "repo:ersahinco/aws-sdlc-containers:ref:refs/heads/main",
    "repo:ersahinco/aws-sdlc-containers:ref:refs/pull/*/head",
  ]

  github_actions_state_bucket_name = "aws-sdlc-containers-tfstate-${local.account_id}"
  github_actions_stack_scope       = "aws-sdlc-containers*"

  github_actions_ecr_push_repositories = [
    module.ecr_app.repository_arn,
    module.ecr_worker.repository_arn,
    module.ecr_liquibase.repository_arn,
    module.ecr_pgbouncer.repository_arn,
  ]

  github_actions_logs_manage_resources = [
    "arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/aws-sdlc-containers*",
    "arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/aws-sdlc-containers*:*",
    "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ecs/*",
    "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ecs/*:*",
  ]

  github_actions_rds_manage_resources = [
    "arn:aws:rds:${local.region}:${local.account_id}:db:${local.github_actions_stack_scope}",
    "arn:aws:rds:${local.region}:${local.account_id}:subgrp:${local.github_actions_stack_scope}",
    "arn:aws:rds:${local.region}:${local.account_id}:pg:${local.github_actions_stack_scope}",
  ]

  github_actions_compute_role_resources = [
    "arn:aws:iam::${local.account_id}:role/${local.github_actions_stack_scope}",
  ]

  github_actions_iam_manage_resources = [
    "arn:aws:iam::${local.account_id}:role/${local.github_actions_stack_scope}",
    "arn:aws:iam::${local.account_id}:policy/${local.github_actions_stack_scope}",
  ]

  github_actions_alb_manage_resources = [
    "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:loadbalancer/app/aws-sdlc-containers*/*",
    "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:targetgroup/aws-sdlc-containers*/*",
    "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:listener/app/aws-sdlc-containers*/*/*",
  ]

  github_actions_acm_certificate_resources = [
    "arn:aws:acm:${local.region}:${local.account_id}:certificate/*",
  ]

  github_actions_route53_zone_resources = [
    "arn:aws:route53:::hostedzone/*",
  ]
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

################################################################################
# Base policy documents
################################################################################

data "aws_iam_policy_document" "github_actions_state_access" {
  statement {
    sid = "TerraformState"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::${local.github_actions_state_bucket_name}",
      "arn:aws:s3:::${local.github_actions_state_bucket_name}/*",
    ]
  }

  statement {
    sid = "TerraformStateLock"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
    ]
    resources = ["arn:aws:dynamodb:${local.region}:${local.account_id}:table/terraform-locks"]
  }
}

data "aws_iam_policy_document" "github_actions_compute_deploy" {
  statement {
    sid = "ECSDeployAndRun"
    actions = [
      "ecs:RegisterTaskDefinition",
      "ecs:DescribeTaskDefinition",
      "ecs:UpdateService",
      "ecs:DescribeServices",
      "ecs:RunTask",
      "ecs:DescribeTasks",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "PassRoleToECS"
    actions   = ["iam:PassRole"]
    resources = local.github_actions_compute_role_resources
  }

  statement {
    sid = "ECSManage"
    actions = [
      "ecs:CreateCluster", "ecs:DeleteCluster", "ecs:UpdateCluster",
      "ecs:CreateService", "ecs:DeleteService", "ecs:UpdateService",
      "ecs:TagResource", "ecs:UntagResource",
    ]
    resources = [
      "arn:aws:ecs:${local.region}:${local.account_id}:cluster/aws-sdlc-containers*",
      "arn:aws:ecs:${local.region}:${local.account_id}:service/aws-sdlc-containers*/*",
      "arn:aws:ecs:${local.region}:${local.account_id}:task-definition/*",
    ]
  }

  statement {
    sid = "ECSDescribeAndRegister"
    actions = [
      "ecs:RegisterTaskDefinition",
      "ecs:DeregisterTaskDefinition",
      "ecs:DescribeTaskDefinition",
      "ecs:DescribeClusters",
      "ecs:DescribeServices",
      "ecs:DescribeTasks",
      "ecs:ListClusters",
      "ecs:ListServices",
      "ecs:ListTaskDefinitions",
      "ecs:ListTagsForResource",
      "ecs:RunTask",
      "ecs:StopTask",
      "ecs:PutClusterCapacityProviders",
    ]
    resources = ["*"]
  }

  statement {
    sid = "AutoScaling"
    actions = [
      "application-autoscaling:RegisterScalableTarget",
      "application-autoscaling:DeregisterScalableTarget",
      "application-autoscaling:DescribeScalableTargets",
      "application-autoscaling:PutScalingPolicy",
      "application-autoscaling:DeleteScalingPolicy",
      "application-autoscaling:DescribeScalingPolicies",
      "application-autoscaling:TagResource",
      "application-autoscaling:UntagResource",
      "application-autoscaling:ListTagsForResource",
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "github_actions_ecr" {
  statement {
    sid       = "ECRAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "ECRPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = local.github_actions_ecr_push_repositories
  }

  statement {
    sid = "ECRPullCrossEnv"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [
      "arn:aws:ecr:${local.region}:${local.account_id}:repository/${local.github_actions_stack_scope}",
    ]
  }

  statement {
    sid = "ECRManage"
    actions = [
      "ecr:CreateRepository", "ecr:DeleteRepository",
      "ecr:PutLifecyclePolicy", "ecr:DeleteLifecyclePolicy", "ecr:GetLifecyclePolicy",
      "ecr:PutImageTagMutability", "ecr:PutImageScanningConfiguration",
      "ecr:SetRepositoryPolicy", "ecr:DeleteRepositoryPolicy",
      "ecr:TagResource", "ecr:UntagResource",
      "ecr:DescribeRepositories", "ecr:GetRepositoryPolicy",
      "ecr:ListTagsForResource",
    ]
    resources = [
      "arn:aws:ecr:${local.region}:${local.account_id}:repository/${local.github_actions_stack_scope}",
    ]
  }
}

data "aws_iam_policy_document" "github_actions_networking" {
  statement {
    sid = "EC2Describe"
    actions = [
      "ec2:Describe*",
      "ec2:Get*",
      "ec2:List*",
    ]
    resources = ["*"]
  }

  statement {
    sid = "EC2Mutate"
    actions = [
      "ec2:CreateVpc", "ec2:DeleteVpc", "ec2:ModifyVpcAttribute",
      "ec2:CreateSubnet", "ec2:DeleteSubnet", "ec2:ModifySubnetAttribute",
      "ec2:CreateRouteTable", "ec2:DeleteRouteTable",
      "ec2:CreateRoute", "ec2:DeleteRoute",
      "ec2:AssociateRouteTable", "ec2:DisassociateRouteTable",
      "ec2:CreateInternetGateway", "ec2:DeleteInternetGateway",
      "ec2:AttachInternetGateway", "ec2:DetachInternetGateway",
      "ec2:AllocateAddress", "ec2:ReleaseAddress", "ec2:AssociateAddress", "ec2:DisassociateAddress",
      "ec2:CreateNatGateway", "ec2:DeleteNatGateway",
      "ec2:CreateSecurityGroup", "ec2:DeleteSecurityGroup",
      "ec2:AuthorizeSecurityGroupIngress", "ec2:RevokeSecurityGroupIngress",
      "ec2:AuthorizeSecurityGroupEgress", "ec2:RevokeSecurityGroupEgress",
      "ec2:UpdateSecurityGroupRuleDescriptionsIngress",
      "ec2:UpdateSecurityGroupRuleDescriptionsEgress",
      "ec2:CreateNetworkAclEntry", "ec2:DeleteNetworkAclEntry", "ec2:ReplaceNetworkAclEntry",
      "ec2:CreateNetworkAcl", "ec2:DeleteNetworkAcl", "ec2:ReplaceNetworkAclAssociation",
      "ec2:CreateTags", "ec2:DeleteTags",
      "ec2:ReplaceRouteTableAssociation",
    ]
    resources = ["*"]
  }

  statement {
    sid = "RDSManage"
    actions = [
      "rds:CreateDBInstance", "rds:DeleteDBInstance", "rds:ModifyDBInstance",
      "rds:RebootDBInstance", "rds:StopDBInstance", "rds:StartDBInstance",
      "rds:CreateDBSubnetGroup", "rds:DeleteDBSubnetGroup", "rds:ModifyDBSubnetGroup",
      "rds:CreateDBParameterGroup", "rds:DeleteDBParameterGroup", "rds:ModifyDBParameterGroup",
      "rds:AddTagsToResource", "rds:RemoveTagsFromResource",
      "rds:ListTagsForResource",
    ]
    resources = local.github_actions_rds_manage_resources
  }

  statement {
    sid       = "RDSDescribe"
    actions   = ["rds:Describe*"]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "github_actions_edge_dns" {
  statement {
    sid = "ALBManage"
    actions = [
      "elasticloadbalancing:CreateLoadBalancer",
      "elasticloadbalancing:DeleteLoadBalancer",
      "elasticloadbalancing:ModifyLoadBalancerAttributes",
      "elasticloadbalancing:SetSecurityGroups",
      "elasticloadbalancing:CreateTargetGroup",
      "elasticloadbalancing:DeleteTargetGroup",
      "elasticloadbalancing:ModifyTargetGroup",
      "elasticloadbalancing:ModifyTargetGroupAttributes",
      "elasticloadbalancing:CreateListener",
      "elasticloadbalancing:DeleteListener",
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:AddTags",
      "elasticloadbalancing:RemoveTags",
    ]
    resources = local.github_actions_alb_manage_resources
  }

  statement {
    sid       = "ALBDescribe"
    actions   = ["elasticloadbalancing:Describe*"]
    resources = ["*"]
  }

  statement {
    sid = "ACMRequestAndList"
    actions = [
      "acm:RequestCertificate",
      "acm:ListCertificates",
    ]
    resources = ["*"]
  }

  statement {
    sid = "ACMManageIssuedCerts"
    actions = [
      "acm:DeleteCertificate",
      "acm:DescribeCertificate",
      "acm:AddTagsToCertificate",
      "acm:RemoveTagsFromCertificate",
      "acm:ListTagsForCertificate",
      "acm:GetCertificate",
    ]
    resources = local.github_actions_acm_certificate_resources
  }

  statement {
    sid = "Route53Read"
    actions = [
      "route53:GetHostedZone",
      "route53:ListHostedZones",
      "route53:ListHostedZonesByName",
      "route53:ListResourceRecordSets",
      "route53:ListTagsForResource",
      "route53:GetChange",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "Route53ChangeRecords"
    actions   = ["route53:ChangeResourceRecordSets"]
    resources = local.github_actions_route53_zone_resources
  }
}

data "aws_iam_policy_document" "github_actions_logs_secrets" {
  statement {
    sid       = "LogsDescribe"
    actions   = ["logs:DescribeLogGroups", "logs:ListTagsForResource", "logs:ListTagsLogGroup"]
    resources = ["*"]
  }

  statement {
    sid = "LogsManage"
    actions = [
      "logs:CreateLogGroup", "logs:DeleteLogGroup",
      "logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy",
      "logs:TagLogGroup", "logs:UntagLogGroup",
      "logs:TagResource", "logs:UntagResource",
    ]
    resources = local.github_actions_logs_manage_resources
  }

  statement {
    sid = "SecretsManagerDescribe"
    actions = [
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:ListSecrets",
      "secretsmanager:ListSecretVersionIds",
    ]
    resources = [
      "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:rds!db-*",
    ]
  }

  statement {
    sid     = "SecretsManagerAPIToken"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:aws-sdlc-containers/api-token*",
    ]
  }

  statement {
    sid = "SecretsManagerRDSManaged"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:TagResource",
      "secretsmanager:PutSecretValue",
      "secretsmanager:DeleteSecret",
    ]
    resources = ["*"]
    condition {
      test     = "StringLike"
      variable = "secretsmanager:Name"
      values   = ["rds!db-*"]
    }
  }
}

data "aws_iam_policy_document" "github_actions_identity_kms" {
  statement {
    sid = "TerraformManageIAM"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:UpdateRole",
      "iam:CreatePolicy", "iam:DeletePolicy",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy", "iam:DetachRolePolicy",
      "iam:TagRole", "iam:UntagRole",
      "iam:TagPolicy", "iam:UntagPolicy",
      "iam:PassRole",
      "iam:GetRole", "iam:GetRolePolicy",
      "iam:GetPolicy", "iam:GetPolicyVersion",
      "iam:ListRolePolicies", "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
    ]
    resources = local.github_actions_iam_manage_resources
  }

  statement {
    sid = "OIDCProviderRead"
    actions = [
      "iam:ListOpenIDConnectProviders",
      "iam:GetOpenIDConnectProvider",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "KMSDescribe"
    actions   = ["kms:DescribeKey", "kms:ListKeys", "kms:ListAliases"]
    resources = ["*"]
  }

  statement {
    sid = "KMSUseRDSKey"
    actions = [
      "kms:CreateGrant",
      "kms:GenerateDataKey",
      "kms:GenerateDataKeyWithoutPlaintext",
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:ReEncryptFrom",
      "kms:ReEncryptTo",
    ]
    resources = ["arn:aws:kms:${local.region}:${local.account_id}:key/*"]
    condition {
      test     = "StringLike"
      variable = "kms:ViaService"
      values   = ["rds.${local.region}.amazonaws.com"]
    }
  }
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

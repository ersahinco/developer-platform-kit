################################################################################
# GitHub Actions OIDC federation
#
# One OIDC provider exists per AWS account (not per environment).
# Bootstrap once with: make bootstrap
#
# The role name follows the project naming convention so the targeted IAM apply
# (make apply-iam-dev / apply-iam-prod) can update trust + permissions without
# running a full plan.
#
# Trust conditions:
#   environment:*        — jobs with a named GitHub Environment
#   ref:refs/heads/main  — push-to-main jobs without an environment
#   ref:refs/pull/*/head — PR plan job
#
# All three sub claim patterns are scoped to this repo only.
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
      values = [
        "repo:ersahinco/db-migration-example:environment:*",
        "repo:ersahinco/db-migration-example:ref:refs/heads/main",
        "repo:ersahinco/db-migration-example:ref:refs/pull/*/head",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${local.name}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "github_actions_permissions" {
  # ── Deploy pipeline (app.yml) ──────────────────────────────────────────

  statement {
    sid       = "ECRAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # GetAuthorizationToken has no resource scope — AWS API limitation
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
    resources = [
      module.ecr_app.repository_arn,
      module.ecr_worker.repository_arn,
      module.ecr_liquibase.repository_arn,
    ]
  }

  # prod-migrate pulls images from dev ECR before pushing to prod ECR.
  # The ECRPush statement above only covers the current environment's repos.
  statement {
    sid = "ECRPullCrossEnv"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [
      "arn:aws:ecr:${local.region}:${local.account_id}:repository/db-migration-example-*",
    ]
  }

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
    resources = ["*"] # RegisterTaskDefinition/DescribeTaskDefinition have no resource scope
  }

  statement {
    sid       = "PassRoleToECS"
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/db-migration-example-*"]
  }

  # ── Infra pipeline (infra.yml) — Terraform state ──────────────────────────

  statement {
    sid = "TerraformState"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::db-migration-example-tfstate-${local.account_id}",
      "arn:aws:s3:::db-migration-example-tfstate-${local.account_id}/*",
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

  # ── Infra pipeline — EC2 / VPC ────────────────────────────────────────────

  statement {
    sid = "EC2Describe"
    actions = [
      "ec2:Describe*",
      "ec2:Get*",
      "ec2:List*",
    ]
    resources = ["*"] # EC2 Describe/Get/List have no resource-level scope — AWS API limitation
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
      # VPC module manages the default Network ACL
      "ec2:CreateNetworkAclEntry", "ec2:DeleteNetworkAclEntry", "ec2:ReplaceNetworkAclEntry",
      "ec2:CreateNetworkAcl", "ec2:DeleteNetworkAcl", "ec2:ReplaceNetworkAclAssociation",
      "ec2:CreateTags", "ec2:DeleteTags",
    ]
    resources = ["*"] # EC2 resource ARNs are not available at creation time — AWS API limitation
  }

  # ── Infra pipeline — RDS ──────────────────────────────────────────────────

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
    resources = [
      "arn:aws:rds:${local.region}:${local.account_id}:db:db-migration-example-*",
      "arn:aws:rds:${local.region}:${local.account_id}:subgrp:db-migration-example-*",
      "arn:aws:rds:${local.region}:${local.account_id}:pg:db-migration-example-*",
    ]
  }

  statement {
    sid       = "RDSDescribe"
    actions   = ["rds:Describe*"]
    resources = ["*"] # RDS Describe calls have no resource-level scope — AWS API limitation
  }

  # ── Infra pipeline — ECS ──────────────────────────────────────────────────

  statement {
    sid = "ECSManage"
    actions = [
      "ecs:CreateCluster", "ecs:DeleteCluster", "ecs:UpdateCluster",
      "ecs:CreateService", "ecs:DeleteService", "ecs:UpdateService",
      "ecs:TagResource", "ecs:UntagResource",
    ]
    resources = [
      "arn:aws:ecs:${local.region}:${local.account_id}:cluster/db-migration-example-*",
      "arn:aws:ecs:${local.region}:${local.account_id}:service/db-migration-example-*/*",
      # TagResource is called on task definitions during RegisterTaskDefinition.
      # The ECS module names the service task definition after the service key ("app"),
      # not the cluster — so we cannot scope to db-migration-example-* here.
      "arn:aws:ecs:${local.region}:${local.account_id}:task-definition/*",
    ]
  }

  statement {
    sid = "ECSDescribeAndRegister"
    actions = [
      "ecs:RegisterTaskDefinition",   # no resource scope — AWS API limitation
      "ecs:DeregisterTaskDefinition", # no resource scope — AWS API limitation
      "ecs:DescribeTaskDefinition",   # no resource scope — AWS API limitation
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
    resources = ["*"] # Describe/Register calls have no resource-level scope — AWS API limitation
  }

  # ── Infra pipeline — ECR ──────────────────────────────────────────────────

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
      "arn:aws:ecr:${local.region}:${local.account_id}:repository/db-migration-example-*",
    ]
  }

  # ── Infra pipeline — ALB ──────────────────────────────────────────────────

  statement {
    sid = "ALBManage"
    actions = [
      "elasticloadbalancing:CreateLoadBalancer",
      "elasticloadbalancing:DeleteLoadBalancer",
      "elasticloadbalancing:ModifyLoadBalancerAttributes",
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
    resources = [
      "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:loadbalancer/app/db-migration-example-*/*",
      "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:targetgroup/db-migration-example-*/*",
      "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:listener/app/db-migration-example-*/*/*",
    ]
  }

  statement {
    sid       = "ALBDescribe"
    actions   = ["elasticloadbalancing:Describe*"]
    resources = ["*"] # ELB Describe calls have no resource-level scope — AWS API limitation
  }

  # ── Infra pipeline — Auto Scaling ─────────────────────────────────────────

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
    resources = ["*"] # DescribeScalableTargets has no resource-level scope — AWS API limitation
  }

  # ── Infra pipeline — CloudWatch Logs ──────────────────────────────────────

  statement {
    sid       = "LogsDescribe"
    actions   = ["logs:DescribeLogGroups", "logs:ListTagsForResource", "logs:ListTagsLogGroup"]
    resources = ["*"] # tag and describe APIs have no resource-level scope — AWS API limitation
  }

  statement {
    sid = "LogsManage"
    actions = [
      "logs:CreateLogGroup", "logs:DeleteLogGroup",
      "logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy",
      "logs:TagLogGroup", "logs:UntagLogGroup",
      "logs:TagResource", "logs:UntagResource",
    ]
    resources = [
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/db-migration-example-*",
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/db-migration-example-*:*",
      # ECS module names container log groups after service/container, not cluster
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ecs/*",
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ecs/*:*",
    ]
  }

  # ── Infra pipeline — Secrets Manager ─────────────────────────────────────

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
    sid = "SecretsManagerRDSManaged"
    # RDS calls these on behalf of the caller when manage_master_user_password=true.
    # CreateSecret is evaluated against * at creation time (secret has no ARN yet).
    # Subsequent operations are scoped to the rds!db-* prefix.
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

  # ── Infra pipeline — IAM ──────────────────────────────────────────────────

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
    resources = [
      "arn:aws:iam::${local.account_id}:role/db-migration-example-*",
      "arn:aws:iam::${local.account_id}:policy/db-migration-example-*",
      # ECS module names task exec roles/policies after the service name ("app")
      "arn:aws:iam::${local.account_id}:role/app-*",
      "arn:aws:iam::${local.account_id}:policy/app-*",
    ]
  }

  statement {
    sid = "OIDCProviderRead"
    actions = [
      "iam:ListOpenIDConnectProviders",
      "iam:GetOpenIDConnectProvider",
    ]
    resources = ["*"] # OIDC provider APIs have no resource-level scope — AWS API limitation
  }

  # ── Infra pipeline — KMS ──────────────────────────────────────────────────

  statement {
    sid       = "KMSDescribe"
    actions   = ["kms:DescribeKey", "kms:ListKeys", "kms:ListAliases"]
    resources = ["*"] # KMS Describe/List have no resource-level scope — AWS API limitation
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
    # aws/rds managed key — used when storage_encrypted=true without a custom key
    resources = ["arn:aws:kms:${local.region}:${local.account_id}:key/*"]
    condition {
      test     = "StringLike"
      variable = "kms:ViaService"
      values   = ["rds.${local.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "github_actions" {
  name   = "github-actions-permissions"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_permissions.json
}

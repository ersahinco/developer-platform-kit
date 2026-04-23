################################################################################
# GitHub Actions OIDC federation
#
# One OIDC provider exists per AWS account.
# Bootstrap once with: make bootstrap
#
# The role name follows the project naming convention so the targeted IAM apply
# can update trust + permissions without running a full plan.
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
        "repo:ersahinco/aws-sdlc-containers:environment:*",
        "repo:ersahinco/aws-sdlc-containers:ref:refs/heads/main",
        "repo:ersahinco/aws-sdlc-containers:ref:refs/pull/*/head",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${local.name}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "github_actions_app" {
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
    resources = [
      module.ecr_app.repository_arn,
      module.ecr_worker.repository_arn,
      module.ecr_liquibase.repository_arn,
      module.ecr_pgbouncer.repository_arn,
    ]
  }

  statement {
    sid = "ECRPullCrossEnv"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [
      "arn:aws:ecr:${local.region}:${local.account_id}:repository/aws-sdlc-containers*",
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
    resources = ["*"]
  }

  statement {
    sid       = "PassRoleToECS"
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/aws-sdlc-containers*"]
  }
}

data "aws_iam_policy_document" "github_actions_state_and_network" {
  statement {
    sid = "TerraformState"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::aws-sdlc-containers-tfstate-${local.account_id}",
      "arn:aws:s3:::aws-sdlc-containers-tfstate-${local.account_id}/*",
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
    resources = [
      "arn:aws:rds:${local.region}:${local.account_id}:db:aws-sdlc-containers*",
      "arn:aws:rds:${local.region}:${local.account_id}:subgrp:aws-sdlc-containers*",
      "arn:aws:rds:${local.region}:${local.account_id}:pg:aws-sdlc-containers*",
    ]
  }

  statement {
    sid       = "RDSDescribe"
    actions   = ["rds:Describe*"]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "github_actions_platform" {
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
      "arn:aws:ecr:${local.region}:${local.account_id}:repository/aws-sdlc-containers*",
    ]
  }

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
    resources = [
      "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:loadbalancer/app/aws-sdlc-containers*/*",
      "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:targetgroup/aws-sdlc-containers*/*",
      "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:listener/app/aws-sdlc-containers*/*/*",
    ]
  }

  statement {
    sid       = "ALBDescribe"
    actions   = ["elasticloadbalancing:Describe*"]
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
    resources = [
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/aws-sdlc-containers*",
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/aws-sdlc-containers*:*",
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ecs/*",
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ecs/*:*",
    ]
  }
}

data "aws_iam_policy_document" "github_actions_security" {
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
      "arn:aws:iam::${local.account_id}:role/aws-sdlc-containers*",
      "arn:aws:iam::${local.account_id}:policy/aws-sdlc-containers*",
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

data "aws_iam_policy_document" "github_actions_dns" {
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
    resources = [
      "arn:aws:acm:${local.region}:${local.account_id}:certificate/*",
    ]
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
    resources = ["arn:aws:route53:::hostedzone/*"]
  }
}

resource "aws_iam_policy" "github_actions_app" {
  name   = "${local.name}-github-actions-app"
  policy = data.aws_iam_policy_document.github_actions_app.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_state_and_network" {
  name   = "${local.name}-github-actions-state-network"
  policy = data.aws_iam_policy_document.github_actions_state_and_network.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_platform" {
  name   = "${local.name}-github-actions-platform"
  policy = data.aws_iam_policy_document.github_actions_platform.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_security" {
  name   = "${local.name}-github-actions-security"
  policy = data.aws_iam_policy_document.github_actions_security.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_dns" {
  name   = "${local.name}-github-actions-dns"
  policy = data.aws_iam_policy_document.github_actions_dns.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_app" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_app.arn
}

resource "aws_iam_role_policy_attachment" "github_actions_state_and_network" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_state_and_network.arn
}

resource "aws_iam_role_policy_attachment" "github_actions_platform" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_platform.arn
}

resource "aws_iam_role_policy_attachment" "github_actions_security" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_security.arn
}

resource "aws_iam_role_policy_attachment" "github_actions_dns" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_dns.arn
}

################################################################################
# ECS task execution role — created explicitly so worker and liquibase task
# definitions can reference it without depending on module.ecs outputs, which
# are null during the same plan that creates those resources.
################################################################################

data "aws_iam_policy_document" "task_exec_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_exec" {
  name               = "${local.name}-task-exec"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "task_exec_managed" {
  role       = aws_iam_role.task_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_exec_secrets" {
  name = "rds-secret-access"
  role = aws_iam_role.task_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = module.rds.db_instance_master_user_secret_arn
    }]
  })
}

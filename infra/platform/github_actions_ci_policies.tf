################################################################################
# GitHub Actions CI IAM policies
#
# Platform owns the single GitHub Actions role and the CI policy attachments.
# App-owned roots attach repository policies to that platform role where a
# workload resource needs a resource policy, but the role identity and managed
# policies stay here.
################################################################################

locals {
  github_actions_stack_scope = "${local.name}*"
  data_hub_bucket_name       = "${local.name}-data-hub-${local.account_id}"

  github_actions_logs_manage_resources = [
    "arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/${local.github_actions_stack_scope}",
    "arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/${local.github_actions_stack_scope}:*",
    "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ecs/*",
    "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ecs/*:*",
  ]

  github_actions_cloudwatch_alarm_resources = [
    "arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:${local.github_actions_stack_scope}",
  ]

  github_actions_rds_manage_resources = [
    "arn:aws:rds:${local.region}:${local.account_id}:db:${local.github_actions_stack_scope}",
    "arn:aws:rds:${local.region}:${local.account_id}:subgrp:${local.github_actions_stack_scope}",
    "arn:aws:rds:${local.region}:${local.account_id}:pg:${local.github_actions_stack_scope}",
  ]

  github_actions_compute_role_resources = [
    "arn:aws:iam::${local.account_id}:role/${local.github_actions_stack_scope}",
    "arn:aws:iam::${local.account_id}:role/app-tasks-*",
  ]

  github_actions_iam_manage_resources = [
    "arn:aws:iam::${local.account_id}:role/${local.github_actions_stack_scope}",
    "arn:aws:iam::${local.account_id}:policy/${local.github_actions_stack_scope}",
  ]

  github_actions_alb_manage_resources = [
    "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:loadbalancer/app/${local.github_actions_stack_scope}/*",
    "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:targetgroup/${local.github_actions_stack_scope}/*",
    "arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:listener/app/${local.github_actions_stack_scope}/*/*",
  ]

  github_actions_acm_certificate_resources = [
    "arn:aws:acm:${local.region}:${local.account_id}:certificate/*",
  ]

  github_actions_route53_zone_resources = [
    "arn:aws:route53:::hostedzone/*",
  ]

  github_actions_data_hub_bucket_resources = [
    "arn:aws:s3:::${local.data_hub_bucket_name}",
  ]

  github_actions_scheduler_resources = [
    "arn:aws:scheduler:${local.region}:${local.account_id}:schedule/default/${local.github_actions_stack_scope}",
  ]

  github_actions_sqs_resources = [
    "arn:aws:sqs:${local.region}:${local.account_id}:${local.github_actions_stack_scope}",
  ]
}

################################################################################
# Base policy documents
################################################################################

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

  statement {
    sid = "SchedulerManage"
    actions = [
      "scheduler:CreateSchedule",
      "scheduler:DeleteSchedule",
      "scheduler:GetSchedule",
      "scheduler:ListTagsForResource",
      "scheduler:TagResource",
      "scheduler:UntagResource",
      "scheduler:UpdateSchedule",
    ]
    resources = local.github_actions_scheduler_resources
  }

  statement {
    sid = "SQSManage"
    actions = [
      "sqs:CreateQueue",
      "sqs:DeleteQueue",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ListQueueTags",
      "sqs:SetQueueAttributes",
      "sqs:TagQueue",
      "sqs:UntagQueue",
    ]
    resources = local.github_actions_sqs_resources
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
    resources = [
      "arn:aws:ecr:${local.region}:${local.account_id}:repository/${local.github_actions_stack_scope}",
    ]
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
      "logs:DeleteMetricFilter", "logs:DescribeMetricFilters",
      "logs:PutMetricFilter",
      "logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy",
      "logs:TagLogGroup", "logs:UntagLogGroup",
      "logs:TagResource", "logs:UntagResource",
    ]
    resources = local.github_actions_logs_manage_resources
  }

  statement {
    sid = "CloudWatchAlarmManage"
    actions = [
      "cloudwatch:DeleteAlarms",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:ListTagsForResource",
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
    ]
    resources = local.github_actions_cloudwatch_alarm_resources
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

data "aws_iam_policy_document" "github_actions_data_hub" {
  statement {
    sid = "DataHubBucketManage"
    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:GetBucketAcl",
      "s3:GetBucketLocation",
      "s3:GetBucketOwnershipControls",
      "s3:GetBucketPublicAccessBlock",
      "s3:GetBucketTagging",
      "s3:GetBucketVersioning",
      "s3:GetEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:ListBucket",
      "s3:PutBucketOwnershipControls",
      "s3:PutBucketPublicAccessBlock",
      "s3:PutBucketTagging",
      "s3:PutBucketVersioning",
      "s3:PutEncryptionConfiguration",
      "s3:PutLifecycleConfiguration",
    ]
    resources = local.github_actions_data_hub_bucket_resources
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

resource "aws_iam_policy" "github_actions_data_hub" {
  name   = "${local.name}-github-actions-data-hub"
  policy = data.aws_iam_policy_document.github_actions_data_hub.json
  tags   = local.tags
}

resource "aws_iam_policy" "github_actions_identity_kms" {
  name   = "${local.name}-github-actions-identity-kms"
  policy = data.aws_iam_policy_document.github_actions_identity_kms.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_managed" {
  for_each = {
    compute_deploy = aws_iam_policy.github_actions_compute_deploy.arn
    ecr            = aws_iam_policy.github_actions_ecr.arn
    networking     = aws_iam_policy.github_actions_networking.arn
    edge_dns       = aws_iam_policy.github_actions_edge_dns.arn
    logs_secrets   = aws_iam_policy.github_actions_logs_secrets.arn
    data_hub       = aws_iam_policy.github_actions_data_hub.arn
    identity_kms   = aws_iam_policy.github_actions_identity_kms.arn
  }

  role       = aws_iam_role.github_actions.name
  policy_arn = each.value
}

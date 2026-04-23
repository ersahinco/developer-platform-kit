################################################################################
# Optional GitHub Actions policy extensions
#
# These attach to the same single GitHub Actions role, but stay separate from
# the base concern policies so optional infrastructure remains easy to review.
################################################################################

################################################################################
# Networking extension — VPC endpoints
################################################################################

data "aws_iam_policy_document" "github_actions_networking_vpc_endpoints" {
  statement {
    sid = "VpcEndpointsManage"
    actions = [
      "ec2:CreateVpcEndpoint",
      "ec2:DeleteVpcEndpoints",
      "ec2:ModifyVpcEndpoint",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "github_actions_networking_vpc_endpoints" {
  name   = "${local.name}-github-actions-networking-vpc-endpoints"
  policy = data.aws_iam_policy_document.github_actions_networking_vpc_endpoints.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_networking_vpc_endpoints" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_networking_vpc_endpoints.arn
}

################################################################################
# Compute extension — ECS Exec from CI
################################################################################

data "aws_iam_policy_document" "github_actions_compute_ecs_exec" {
  statement {
    sid       = "ECSExec"
    actions   = ["ecs:ExecuteCommand"]
    resources = ["*"]
  }

  statement {
    sid = "SSMExec"
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "github_actions_compute_ecs_exec" {
  name   = "${local.name}-github-actions-compute-ecs-exec"
  policy = data.aws_iam_policy_document.github_actions_compute_ecs_exec.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_compute_ecs_exec" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_compute_ecs_exec.arn
}

################################################################################
# Edge extension — WAF
################################################################################

data "aws_iam_policy_document" "github_actions_edge_waf" {
  statement {
    sid = "WAFManage"
    actions = [
      "wafv2:CreateWebACL", "wafv2:DeleteWebACL", "wafv2:UpdateWebACL",
      "wafv2:GetWebACL", "wafv2:ListWebACLs",
      "wafv2:AssociateWebACL", "wafv2:DisassociateWebACL", "wafv2:GetWebACLForResource",
      "wafv2:ListResourcesForWebACL",
      "wafv2:TagResource", "wafv2:UntagResource", "wafv2:ListTagsForResource",
      "wafv2:CheckCapacity",
      "wafv2:DescribeManagedRuleGroup",
      "wafv2:ListAvailableManagedRuleGroups",
      "wafv2:ListAvailableManagedRuleGroupVersions",
    ]
    resources = [
      "arn:aws:wafv2:${local.region}:${local.account_id}:regional/webacl/aws-sdlc-containers*/*",
      "arn:aws:wafv2:${local.region}:${local.account_id}:regional/managedruleset/*/*",
    ]
  }

  statement {
    sid = "WAFDescribe"
    actions = [
      "wafv2:ListWebACLs",
      "wafv2:ListAvailableManagedRuleGroups",
      "wafv2:ListAvailableManagedRuleGroupVersions",
      "wafv2:DescribeManagedRuleGroup",
      "wafv2:CheckCapacity",
      "wafv2:GetWebACLForResource",
      "wafv2:ListResourcesForWebACL",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "github_actions_edge_waf" {
  name   = "${local.name}-github-actions-edge-waf"
  policy = data.aws_iam_policy_document.github_actions_edge_waf.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_edge_waf" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_edge_waf.arn
}

################################################################################
# ECS Exec — SSM permissions on the app task role
# Required for `aws ecs execute-command` and SSM port forwarding to RDS.
# No bastion host needed — SSM tunnels through the running Fargate task.
################################################################################

resource "aws_iam_role_policy" "task_ssm_exec" {
  name = "ssm-exec"
  role = module.ecs.services["app"].tasks_iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel",
      ]
      Resource = "*" # ssmmessages has no resource-level scope — AWS API limitation
    }]
  })
}

################################################################################
# Optional IAM boundaries
#
# These policies line up with the optional infrastructure files so the base
# deployment role stays focused on the lean stack and the extras remain
# explicitly opt-in, even though they default to enabled in this phase.
################################################################################

data "aws_iam_policy_document" "github_actions_vpc_endpoints" {
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

resource "aws_iam_policy" "github_actions_vpc_endpoints" {
  name   = "${local.name}-github-actions-vpc-endpoints"
  policy = data.aws_iam_policy_document.github_actions_vpc_endpoints.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_vpc_endpoints" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_vpc_endpoints.arn
}

data "aws_iam_policy_document" "github_actions_ecs_exec" {
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

resource "aws_iam_policy" "github_actions_ecs_exec" {
  name   = "${local.name}-github-actions-ecs-exec"
  policy = data.aws_iam_policy_document.github_actions_ecs_exec.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_ecs_exec" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_ecs_exec.arn
}

data "aws_iam_policy_document" "github_actions_waf" {
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

resource "aws_iam_policy" "github_actions_waf" {
  name   = "${local.name}-github-actions-waf"
  policy = data.aws_iam_policy_document.github_actions_waf.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_waf" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_waf.arn
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

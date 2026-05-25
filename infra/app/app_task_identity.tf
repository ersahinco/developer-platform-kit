################################################################################
# Primary edge task identity
#
# Single deterministic role used by all repo-sourced task definitions.
# The legacy name_prefix role (primary-edge-tasks-*) was retired after the
# live service rolled onto this role via app-deploy.
################################################################################

data "aws_iam_policy_document" "primary_edge_task_assume" {
  statement {
    sid     = "ECSTasksAssumeRole"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:ecs:${local.region}:${local.account_id}:*"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

data "aws_iam_policy_document" "primary_edge_task" {
  statement {
    sid = "ECSExec"
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "primary_edge_task_deploy" {
  name        = "${local.name}-primary-edge-task"
  description = "IAM role for primary edge ECS task definitions"

  assume_role_policy    = data.aws_iam_policy_document.primary_edge_task_assume.json
  force_detach_policies = true

  tags = local.tags
}

resource "aws_iam_policy" "primary_edge_task_deploy" {
  name        = "${local.name}-primary-edge-task-policy"
  description = "Task role IAM policy for primary edge task definitions"
  policy      = data.aws_iam_policy_document.primary_edge_task.json

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "primary_edge_task_deploy_internal" {
  role       = aws_iam_role.primary_edge_task_deploy.name
  policy_arn = aws_iam_policy.primary_edge_task_deploy.arn
}

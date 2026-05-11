################################################################################
# App task identity
#
# The app task role is root-owned so the ECS service module can stop managing
# app task-definition revisions after bootstrap without also dropping runtime
# IAM ownership.
################################################################################

moved {
  from = module.ecs.module.service["app"].aws_iam_role.tasks[0]
  to   = aws_iam_role.app_task
}

moved {
  from = module.ecs.module.service["app"].aws_iam_policy.tasks[0]
  to   = aws_iam_policy.app_task
}

moved {
  from = module.ecs.module.service["app"].aws_iam_role_policy_attachment.tasks_internal[0]
  to   = aws_iam_role_policy_attachment.app_task_internal
}

data "aws_iam_policy_document" "app_task_assume" {
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

resource "aws_iam_role" "app_task" {
  name_prefix = "app-tasks-"
  description = "IAM role for ECS tasks in Service app"

  assume_role_policy    = data.aws_iam_policy_document.app_task_assume.json
  force_detach_policies = true

  tags = local.tags
}

data "aws_iam_policy_document" "app_task" {
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

resource "aws_iam_policy" "app_task" {
  name_prefix = "app-tasks-"
  description = "Task role IAM policy"
  policy      = data.aws_iam_policy_document.app_task.json

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "app_task_internal" {
  role       = aws_iam_role.app_task.name
  policy_arn = aws_iam_policy.app_task.arn
}

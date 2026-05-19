################################################################################
# Api task identity
#
# The api task role is root-owned so the ECS service module can stop managing
# api task-definition revisions after bootstrap without also dropping runtime
# IAM ownership.
################################################################################

data "aws_iam_policy_document" "api_task_assume" {
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

resource "aws_iam_role" "api_task" {
  name_prefix = "api-tasks-"
  description = "IAM role for ECS tasks in Service api"

  assume_role_policy    = data.aws_iam_policy_document.api_task_assume.json
  force_detach_policies = true

  tags = local.tags
}

data "aws_iam_policy_document" "api_task" {
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

resource "aws_iam_policy" "api_task" {
  name_prefix = "api-tasks-"
  description = "Task role IAM policy"
  policy      = data.aws_iam_policy_document.api_task.json

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "api_task_internal" {
  role       = aws_iam_role.api_task.name
  policy_arn = aws_iam_policy.api_task.arn
}

################################################################################
# Runtime identity
#
# GitHub Actions OIDC lives in infra/platform. This file keeps shared ECS task
# execution identity for workloads after deployment. Workload-specific task role
# policies stay next to the workload capability that needs them.
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

data "aws_iam_policy_document" "task_exec_secrets" {
  statement {
    sid       = "ReadRDSMasterSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [module.rds.db_instance_master_user_secret_arn]
  }
}

resource "aws_iam_role_policy" "task_exec_secrets" {
  name   = "rds-secret-access"
  role   = aws_iam_role.task_exec.id
  policy = data.aws_iam_policy_document.task_exec_secrets.json
}

data "aws_iam_policy_document" "firelens_cloudwatch_logs" {
  statement {
    sid = "WriteFireLensCloudWatchLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/${local.name}/*:*"]
  }
}

resource "aws_iam_policy" "firelens_cloudwatch_logs" {
  name   = "${local.name}-firelens-cloudwatch-logs"
  policy = data.aws_iam_policy_document.firelens_cloudwatch_logs.json
  tags   = local.tags
}

resource "aws_iam_role_policy_attachment" "app_firelens_cloudwatch_logs" {
  role       = aws_iam_role.app_task.name
  policy_arn = aws_iam_policy.firelens_cloudwatch_logs.arn
}

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
    sid       = "ReadDatabaseRuntimeSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [module.rds.db_instance_master_user_secret_arn]
  }

  statement {
    sid     = "ReadPrimaryEdgeAuthToken"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:${local.primary_edge_auth_token_secret_name}*"
    ]
  }

  statement {
    sid = "ReadPrimaryEdgeAuthTokenParameter"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = [
      "arn:aws:ssm:${local.region}:${local.account_id}:parameter/${local.primary_edge_auth_token_secret_name}"
    ]
  }
}

resource "aws_iam_role_policy" "task_exec_secrets" {
  name   = "runtime-secret-access"
  role   = aws_iam_role.task_exec.id
  policy = data.aws_iam_policy_document.task_exec_secrets.json
}

################################################################################
# Workload runtime IAM
#
# GitHub Actions OIDC lives in the `oidc_*.tf` files. This file keeps the ECS
# task execution role definitions that are assumed after deployment.
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

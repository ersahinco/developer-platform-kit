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

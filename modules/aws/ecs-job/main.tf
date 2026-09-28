################################################################################
# ECS job
#
# One bounded task: log group, roles, and task definition.
# The data lane runs migrations on demand.
#
# A job is only safe here if it exits non-zero on failure and can be rerun.
# Neither property can be enforced from Terraform, so both belong in the job's
# own tests and its README.
################################################################################

data "aws_region" "current" {}

data "aws_vpc" "this" {
  id = var.vpc_id
}

data "aws_ec2_managed_prefix_list" "s3" {
  name = "com.amazonaws.${data.aws_region.current.region}.s3"
}

locals {
  log_group_name = coalesce(var.log_group_name, "/ecs/${var.name}")

  # A secret value may carry a JSON key suffix, as in "<arn>:password::". That is
  # valid for the container definition and invalid as an IAM resource, so the
  # policy gets the ARN back without it.
  secret_resources = distinct([
    for arn in values(var.secrets) :
    join(":", slice(split(":", arn), 0, min(7, length(split(":", arn)))))
  ])

  container = {
    name      = var.container_name
    image     = var.image
    essential = true
    command   = var.command
    environment = [
      for key in sort(keys(var.environment)) : {
        name  = key
        value = var.environment[key]
      }
    ]
    secrets = [
      for key in sort(keys(var.secrets)) : {
        name      = key
        valueFrom = var.secrets[key]
      }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = local.log_group_name
        "awslogs-region"        = data.aws_region.current.region
        "awslogs-stream-prefix" = var.container_name
      }
    }
  }
}

resource "aws_cloudwatch_log_group" "this" {
  # checkov:skip=CKV_AWS_338:Retention is a consumer cost/compliance choice; default 30 days, set log_retention_days to 365 for annual retention.

  name              = local.log_group_name
  retention_in_days = var.log_retention_days
  kms_key_id        = var.log_kms_key_arn

  tags = var.tags
}

data "aws_iam_policy_document" "assume_task" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name}-execution"
  description        = "Pulls images, reads injected secrets, and writes logs for ${var.name}"
  assume_role_policy = data.aws_iam_policy_document.assume_task.json

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  count = length(var.secrets) == 0 ? 0 : 1

  statement {
    sid       = "ReadInjectedSecrets"
    actions   = ["secretsmanager:GetSecretValue", "ssm:GetParameters"]
    resources = local.secret_resources
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  count = length(var.secrets) == 0 ? 0 : 1

  name   = "${var.name}-secret-injection"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets[0].json
}

resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  description        = "Runtime identity for ${var.name}"
  assume_role_policy = data.aws_iam_policy_document.assume_task.json

  tags = var.tags
}

resource "aws_iam_role_policy" "task" {
  for_each = var.task_policy_json

  name   = each.key
  role   = aws_iam_role.task.id
  policy = each.value
}

resource "aws_iam_role_policy_attachment" "task_managed" {
  for_each = var.task_policy_arns

  role       = aws_iam_role.task.name
  policy_arn = each.value
}

resource "aws_ecs_task_definition" "this" {
  # checkov:skip=CKV_AWS_336:Liquibase requires writable temporary files; this starter runs a bounded migration task without host mounts.

  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    cpu_architecture        = var.cpu_architecture
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([local.container])

  tags = var.tags
}

resource "aws_security_group" "task" {
  # checkov:skip=CKV2_AWS_5:The delivery lane attaches this exported group when starting a task.

  name_prefix = "${var.name}-task-"
  description = "Task network placement for ${var.name}"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

moved {
  from = aws_vpc_security_group_egress_rule.all
  to   = aws_vpc_security_group_egress_rule.endpoints
}

resource "aws_vpc_security_group_egress_rule" "endpoints" {
  security_group_id = aws_security_group.task.id
  description       = "HTTPS to private AWS endpoints; dependencies use separate client groups"
  cidr_ipv4         = data.aws_vpc.this.cidr_block
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "s3" {
  security_group_id = aws_security_group.task.id
  description       = "HTTPS to S3, including ECR image layers"
  prefix_list_id    = data.aws_ec2_managed_prefix_list.s3.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

# Terraform owns service configuration and task count; delivery owns image revisions.

data "aws_region" "current" {}

data "aws_vpc" "this" {
  id = var.vpc_id
}

data "aws_ec2_managed_prefix_list" "s3" {
  name = "com.amazonaws.${data.aws_region.current.region}.s3"
}

locals {
  log_group_name = coalesce(var.log_group_name, "/ecs/${var.name}")

  # Strip container-only JSON key suffixes (e.g. :password::) from IAM resource ARNs.
  secret_resources = distinct([
    for arn in values(var.secrets) :
    join(":", slice(split(":", arn), 0, min(7, length(split(":", arn)))))
  ])

  container = merge(
    {
      name      = var.container_name
      image     = var.image
      essential = true
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
    },
    var.container_port == null ? {} : {
      portMappings = [{
        containerPort = var.container_port
        protocol      = "tcp"
      }]
    },
    var.health_check_command == null ? {} : {
      healthCheck = {
        command     = var.health_check_command
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
    },
  )
}

resource "aws_cloudwatch_log_group" "this" {
  # checkov:skip=CKV_AWS_338:Retention is a consumer cost/compliance choice; default 30 days, set log_retention_days to 365 for annual retention.

  name              = local.log_group_name
  retention_in_days = var.log_retention_days
  kms_key_id        = var.log_kms_key_arn

  tags = var.tags
}

# Identity

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

# Task definition

resource "aws_ecs_task_definition" "this" {
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

# Network placement

resource "aws_security_group" "task" {
  name_prefix = "${var.name}-task-"
  description = "Task network placement for ${var.name}"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "from_load_balancer" {
  count = var.load_balancer_security_group_id == null ? 0 : 1

  security_group_id            = aws_security_group.task.id
  description                  = "Load balancer to container port"
  referenced_security_group_id = var.load_balancer_security_group_id
  from_port                    = var.container_port
  to_port                      = var.container_port
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "from_peers" {
  for_each = toset(var.ingress_security_group_ids)

  security_group_id            = aws_security_group.task.id
  description                  = "Peer workload to container port"
  referenced_security_group_id = each.value
  from_port                    = var.container_port
  to_port                      = var.container_port
  ip_protocol                  = "tcp"
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

# Service

resource "aws_ecs_service" "this" {
  name            = var.name
  cluster         = var.cluster_id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = var.capacity_provider == null ? "FARGATE" : null

  enable_execute_command = var.enable_execute_command
  propagate_tags         = "SERVICE"

  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent
  health_check_grace_period_seconds  = var.target_group_arn == null ? null : var.health_check_grace_period_seconds

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = concat([aws_security_group.task.id], var.extra_security_group_ids)
    assign_public_ip = false
  }

  dynamic "capacity_provider_strategy" {
    for_each = var.capacity_provider == null ? [] : [1]
    content {
      capacity_provider = var.capacity_provider
      weight            = 100
    }
  }

  dynamic "load_balancer" {
    for_each = var.target_group_arn == null ? [] : [1]
    content {
      target_group_arn = var.target_group_arn
      container_name   = var.container_name
      container_port   = var.container_port
    }
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [task_definition]

    precondition {
      condition     = var.target_group_arn == null || var.container_port != null
      error_message = "A service behind a target group needs container_port set."
    }
  }
}

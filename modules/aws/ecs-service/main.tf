################################################################################
# ECS service
#
# One long-running workload: log group, task roles, task definition, security
# group, service, and optional target-group registration and autoscaling.
#
# Terraform owns the shape of the service. The deploy lane owns which image is
# running, so task_definition and desired_count are ignored after creation.
# Changing the container shape here and deploying an image there stay separate
# on purpose.
################################################################################

data "aws_region" "current" {}

locals {
  log_group_name = coalesce(var.log_group_name, "/ecs/${var.name}")

  # A secret value may carry a JSON key suffix, as in "<arn>:password::". That is
  # valid for the container definition and invalid as an IAM resource, so the
  # policy gets the ARN back without it.
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

################################################################################
# Identity
################################################################################

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

################################################################################
# Task definition
################################################################################

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

################################################################################
# Network placement
################################################################################

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

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.task.id
  description       = "Outbound to AWS APIs, endpoints, and dependencies"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

################################################################################
# Service
################################################################################

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

  dynamic "service_registries" {
    for_each = var.service_discovery_arn == null ? [] : [1]
    content {
      registry_arn = var.service_discovery_arn
    }
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [task_definition, desired_count]

    precondition {
      condition     = var.target_group_arn == null || var.container_port != null
      error_message = "A service behind a target group needs container_port set."
    }
  }
}

################################################################################
# Autoscaling
################################################################################

resource "aws_appautoscaling_target" "this" {
  count = var.autoscaling == null ? 0 : 1

  service_namespace  = "ecs"
  resource_id        = "service/${var.cluster_name}/${aws_ecs_service.this.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = var.autoscaling.min_capacity
  max_capacity       = var.autoscaling.max_capacity

  tags = var.tags
}

resource "aws_appautoscaling_policy" "cpu" {
  count = var.autoscaling == null ? 0 : 1

  name               = "${var.name}-cpu"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.this[0].service_namespace
  resource_id        = aws_appautoscaling_target.this[0].resource_id
  scalable_dimension = aws_appautoscaling_target.this[0].scalable_dimension

  target_tracking_scaling_policy_configuration {
    target_value       = var.autoscaling.target_cpu_percent
    scale_in_cooldown  = 300
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

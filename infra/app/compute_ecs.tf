################################################################################
# App compute — ECS service
################################################################################

locals {
  primary_edge_task_container_definitions = merge(local.adot_collector_container, {
    # PgBouncer sidecar — runs in the same task network namespace as the app.
    # The app's DATABASE_URL points to localhost:5432 (pgbouncer), not RDS directly.
    # transaction mode: server connections are returned to the pool after each
    # transaction, multiplexing many app connections onto a small RDS pool.
    # pgbouncer connects to RDS using the secret injected via DB_HOST / DB_PORT /
    # DB_NAME / DB_USER / DB_PASSWORD environment variables.
    pgbouncer = {
      # Built from edoburu/pgbouncer:v1.25.1-p0 with Alpine security updates,
      # then pushed to ECR by CI to avoid Docker Hub pull rate limits.
      image          = format("%s:%s", module.ecr["pgbouncer"].repository_url, "v1.25.1-p0")
      essential      = true
      systemControls = []
      volumesFrom    = []

      # pgbouncer's entrypoint generates /etc/pgbouncer/userlist.txt and pgbouncer.ini
      # at startup. readonlyRootFilesystem must be false — the entrypoint writes to
      # multiple paths (/etc/pgbouncer, /var/run/pgbouncer) that cannot all be covered
      # by volume mounts without overcomplicating the config.
      readonlyRootFilesystem = false

      # RDS-managed secret only contains username + password.
      # Host, port, dbname are not sensitive — injected as plain env vars below.
      secrets = [
        { name = "DB_USER", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
      ]

      environment = [
        { name = "DB_HOST", value = module.rds.db_instance_address },
        { name = "DB_PORT", value = tostring(module.rds.db_instance_port) },
        { name = "DB_NAME", value = "aws_sdlc_containers" },
        { name = "POOL_MODE", value = "transaction" },
        { name = "DEFAULT_POOL_SIZE", value = tostring(var.pgbouncer_pool_size) },
        { name = "MAX_CLIENT_CONN", value = "200" },
        { name = "AUTH_TYPE", value = "scram-sha-256" },
        # Log pool stats once per hour instead of every 60 s — reduces CloudWatch
        # noise when traffic is low while preserving the signal for pool pressure
        # diagnosis. Set to 0 to disable entirely if stats are never needed.
        { name = "STATS_PERIOD", value = "3600" },
      ]

      enable_cloudwatch_logging              = true
      cloudwatch_log_group_retention_in_days = 14
      cloudwatch_log_group_kms_key_id        = aws_kms_key.cloudwatch_logs.arn
      # Explicit name keeps the log group stack-scoped and readable instead of
      # relying on the module's generic service-key-derived default.
      cloudwatch_log_group_name = "/ecs/${local.name}/pgbouncer"
    }

    (local.primary_edge_repository) = {
      # Documentation-only container shape after the ownership migration:
      # GitHub Actions renders and registers real app task-definition
      # revisions. See docs/runbooks/app-infra-ownership.md.
      image = format(
        "%s:%s",
        module.ecr[local.primary_edge_workload_name].repository_url,
        coalesce(var.primary_edge_image_tag, var.bootstrap_image_tag)
      )
      essential = true

      # ECS container definition keys are camelCase — they map directly to the ECS API
      portMappings   = [{ containerPort = local.primary_edge_service_port, hostPort = local.primary_edge_service_port, protocol = "tcp" }]
      systemControls = []
      volumesFrom    = []

      # ECS does not interpolate $(VAR) in environment values. DB_PASSWORD is
      # injected as a secret; the app's config.py composes DATABASE_URL at startup.
      secrets     = local.workload_secrets[local.primary_edge_workload_name]
      environment = local.workload_environment[local.primary_edge_workload_name]

      # pgbouncer must be accepting connections before the app starts.
      dependsOn = concat(
        [{ containerName = "pgbouncer", condition = "START" }],
        var.enable_adot_sidecar ? [{ containerName = "adot", condition = "START" }] : []
      )

      healthCheck = {
        command = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${local.primary_edge_service_port}/health')\""]
        # 5s interval, startPeriod covers Fargate cold start (~15s).
        # After startPeriod, 2 × 5s = 10s to mark healthy.
        interval    = 5
        timeout     = 3
        retries     = 3
        startPeriod = 15
      }

      # readonlyRootFilesystem = false: ECS Exec (SSM agent) requires write access to
      # /var/lib/amazon and /var/log/amazon at startup — it does not support readonly
      # root even with tmpfs mounts on Fargate 1.4. The module defaults to true, so
      # we explicitly opt out. The meaningful security boundary here is IAM + network
      # (private subnet, security groups), not filesystem immutability.
      readonlyRootFilesystem = false

      enable_cloudwatch_logging              = true
      cloudwatch_log_group_retention_in_days = 30
      cloudwatch_log_group_kms_key_id        = aws_kms_key.cloudwatch_logs.arn
      # Explicit name keeps the log group stack-scoped and readable instead of
      # relying on the module's generic service-key-derived default.
      cloudwatch_log_group_name = local.workload_log_group_names[local.primary_edge_workload_name]
    }
  })

  primary_edge_task_definition_containers = [
    for name, definition in local.primary_edge_task_container_definitions :
    merge(definition, { name = name })
  ]
}

################################################################################
# ECS — terraform-aws-modules/ecs/aws ~> 7.0
# v7: cluster_capacity_providers must be explicit — no longer inferred.
# task_exec_secret_arns is top-level — wires the shared execution role to the
# RDS secret so ECS can inject DB credentials into task definitions without
# AWS SDK calls from the containers.
# Terraform owns the ECS service shape, deployment circuit breaker, deployment
# alarms, networking, and IAM.
# After bootstrap, GitHub Actions owns app task-definition revisions and app
# image roll-forward/rollback. Terraform points the service at the current
# family only for create/read purposes and ignores service task-definition drift.
################################################################################

resource "aws_ecs_task_definition" "primary_edge" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.primary_edge_cpu
  memory                   = var.primary_edge_memory
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.primary_edge_task_deploy.arn
  container_definitions    = jsonencode(local.primary_edge_task_definition_containers)

  tags = local.tags
}

data "aws_ecs_task_definition" "primary_edge_current" {
  depends_on      = [aws_ecs_task_definition.primary_edge]
  task_definition = local.name
}

module "ecs" {
  source  = "terraform-aws-modules/ecs/aws"
  version = "~> 7.0"

  cluster_name = local.name

  cluster_capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  default_capacity_provider_strategy = {
    FARGATE = { weight = 1, base = 1 }
  }

  # Top-level in v7 — grants the shared execution role access to the RDS secret.
  task_exec_secret_arns = [module.rds.db_instance_master_user_secret_arn]

  tags = local.tags
}

resource "aws_ecs_service" "primary_edge" {
  name            = local.primary_edge_repository
  cluster         = module.ecs.cluster_arn
  task_definition = data.aws_ecs_task_definition.primary_edge_current.arn
  desired_count   = var.primary_edge_bootstrap_desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 15
  enable_execute_command             = true

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_configuration {
    strategy             = "ROLLING"
    bake_time_in_minutes = "5"
  }

  dynamic "alarms" {
    for_each = var.enable_primary_edge_symptom_cloudwatch_alarms ? [1] : []

    content {
      alarm_names = [
        aws_cloudwatch_metric_alarm.primary_edge_target_5xx[0].alarm_name,
        aws_cloudwatch_metric_alarm.primary_edge_target_latency[0].alarm_name,
      ]
      enable   = true
      rollback = true
    }
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.primary_edge.arn
    container_name   = local.primary_edge_repository
    container_port   = local.primary_edge_service_port
  }

  network_configuration {
    assign_public_ip = false
    security_groups  = [aws_security_group.primary_edge.id]
    subnets          = local.platform.private_subnet_ids
  }

  # Terraform bootstraps the service shape. The deploy workflow owns later
  # task-definition revisions, desired rollout settings, and activates the
  # service with a verified image.
  lifecycle {
    ignore_changes = [
      desired_count,
      task_definition,
    ]
  }

  tags = local.tags
}

################################################################################
# ECS Exec — SSM permissions on the app task role
#
# This belongs with the app ECS service because it is an operational capability
# of that service. It supports `aws ecs execute-command` and SSM port forwarding
# to RDS without a bastion host.
################################################################################

resource "aws_iam_role_policy" "primary_edge_task_deploy_ssm_exec" {
  name = "ssm-exec"
  role = aws_iam_role.primary_edge_task_deploy.name

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
      Resource = "*"
    }]
  })
}

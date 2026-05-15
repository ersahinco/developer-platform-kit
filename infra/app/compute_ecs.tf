################################################################################
# App compute — ECS service
################################################################################

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

data "aws_ecs_task_definition" "app_current" {
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

  services = {
    app = {
      cpu    = var.app_cpu
      memory = var.app_memory

      desired_count                      = var.app_desired_count
      deployment_minimum_healthy_percent = 100
      deployment_maximum_percent         = 200
      deployment_circuit_breaker = {
        enable   = true
        rollback = true
      }
      deployment_configuration = {
        strategy             = "ROLLING"
        bake_time_in_minutes = "5"
      }
      create_infrastructure_iam_role = false
      alarms = var.enable_app_symptom_cloudwatch_alarms ? {
        alarm_names = [
          aws_cloudwatch_metric_alarm.app_target_5xx[0].alarm_name,
          aws_cloudwatch_metric_alarm.app_target_latency[0].alarm_name,
        ]
        enable   = true
        rollback = true
      } : null
      ignore_task_definition_changes = true
      # Grace period prevents the ALB from health-checking the new task before the
      # app is listening. Without this (default 0), the ALB marks the task unhealthy
      # immediately on registration and ECS stalls the deploy waiting for recovery.
      # 15s: Fargate cold start is typically 10-20s; app starts in <2s after that.
      # Lower than 15s risks false-unhealthy on cold starts and stalls the deploy.
      health_check_grace_period_seconds = 15

      # Use the explicitly managed execution role so our secret policy applies.
      # Without this the module creates its own role that lacks GetSecretValue.
      create_task_exec_iam_role = false
      task_exec_iam_role_arn    = aws_iam_role.task_exec.arn
      # Enables `aws ecs execute-command` for interactive access to running tasks.
      # Required for DB access via SSM port forwarding — no bastion needed.
      enable_execute_command = true
      create_task_definition = false
      task_definition_arn    = data.aws_ecs_task_definition.app_current.arn
      create_tasks_iam_role  = false
      tasks_iam_role_arn     = aws_iam_role.app_task.arn
      # Explicit family name — module default uses the service key ("app") which
      # is shared by multiple containers in the task. Scoping to local.name keeps
      # the stack self-contained.
      family = local.name

      container_definitions = merge(local.adot_collector_container, {
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

        app = {
          # Documentation-only container shape after the ownership migration:
          # GitHub Actions renders and registers real app task-definition
          # revisions. See docs/runbooks/app-infra-ownership.md.
          image     = format("%s:%s", module.ecr["app"].repository_url, coalesce(var.app_image_tag, var.initial_image_tag))
          essential = true

          # ECS container definition keys are camelCase — they map directly to the ECS API
          portMappings   = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
          systemControls = []
          volumesFrom    = []

          # ECS does not interpolate $(VAR) in environment values. DB_PASSWORD is
          # injected as a secret; the app's config.py composes DATABASE_URL at startup.
          secrets = [
            { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
          ]

          environment = concat([
            { name = "ROLLOUT_DRILL_FAULT_MODE", value = "off" },
            { name = "ROLLOUT_DRILL_FAULT_PATHS", value = "/ready" },
            { name = "ROLLOUT_DRILL_FAULT_DELAY_SECONDS", value = "3" },
            { name = "ROLLOUT_DRILL_FAULT_STATUS_CODE", value = "503" },
            ], var.enable_adot_sidecar ? [
            { name = "OTEL_TRACES_ENABLED", value = "true" },
            { name = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", value = "http://127.0.0.1:4318/v1/traces" },
            { name = "OTEL_SERVICE_NAME", value = "aws-sdlc-containers-api" },
            { name = "OTEL_DEPLOYMENT_ENVIRONMENT", value = "aws" },
            ] : [], (!var.enable_adot_sidecar && var.otel_exporter_otlp_traces_endpoint != null) ? [
            { name = "OTEL_TRACES_ENABLED", value = "true" },
            { name = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", value = var.otel_exporter_otlp_traces_endpoint },
            { name = "OTEL_SERVICE_NAME", value = "aws-sdlc-containers-api" },
            { name = "OTEL_DEPLOYMENT_ENVIRONMENT", value = "aws" },
          ] : [])

          # pgbouncer must be accepting connections before the app starts.
          dependsOn = concat(
            [{ containerName = "pgbouncer", condition = "START" }],
            var.enable_adot_sidecar ? [{ containerName = "adot", condition = "START" }] : []
          )

          healthCheck = {
            command = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\""]
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
          cloudwatch_log_group_name = "/ecs/${local.name}/app"
        }
      })

      load_balancer = {
        service = {
          target_group_arn = aws_lb_target_group.app.arn
          container_name   = "app"
          container_port   = 8000
        }
      }

      subnet_ids = local.platform.private_subnet_ids
      vpc_id     = local.platform.vpc_id

      # Use the pre-created SG so RDS can reference it without a circular
      # dependency (RDS SG → app SG → ECS module → RDS endpoint → RDS → RDS SG).
      create_security_group = false
      security_group_ids    = [aws_security_group.app.id]

      service_registries = null
    }
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

resource "aws_iam_role_policy" "task_ssm_exec" {
  name = "ssm-exec"
  role = aws_iam_role.app_task.name

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

################################################################################
# Base compute — core repositories and ECS service
################################################################################

################################################################################
# ECR — terraform-aws-modules/ecr/aws ~> 3.0
# IMMUTABLE tags prevent silent overwrites of a deployed SHA.
# scan_on_push enables free basic CVE scanning on every push.
# Lifecycle: expire untagged after 1 day, keep last 10 sha- tagged images.
################################################################################

module "ecr_app" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 3.0"

  repository_name                 = "${local.name}/app"
  repository_image_tag_mutability = "IMMUTABLE"
  repository_image_scan_on_push   = true

  repository_read_write_access_arns = [local.github_actions_role_arn]

  repository_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day "
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep last 10 sha- tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["sha-"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = { type = "expire" }
      }
    ]
  })

  tags = local.tags
}

################################################################################
# ECR — pgbouncer sidecar image (mirrored from Docker Hub)
# Avoids Docker Hub unauthenticated pull rate limits (100 pulls/6h per NAT IP).
# CI mirrors the upstream tag once; ECS pulls from ECR with no rate limit.
################################################################################

module "ecr_pgbouncer" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 3.0"

  repository_name                 = "${local.name}/pgbouncer"
  repository_image_tag_mutability = "IMMUTABLE"
  repository_image_scan_on_push   = true

  repository_read_write_access_arns = [local.github_actions_role_arn]

  repository_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep last 5 tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = { type = "expire" }
      }
    ]
  })

  tags = local.tags
}

################################################################################
# ECS — terraform-aws-modules/ecs/aws ~> 7.0
# v7: cluster_capacity_providers must be explicit — no longer inferred.
# task_exec_secret_arns is top-level — wires the shared execution role to the
# RDS secret so ECS can inject DB credentials into task definitions without
# AWS SDK calls from the containers.
# ignore_task_definition_changes prevents terraform apply from rolling back
# the image tag after GitHub Actions has deployed a newer one.
################################################################################

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
      ignore_task_definition_changes     = true
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
      # Explicit family name — module default uses the service key ("app") which
      # is shared by multiple containers in the task. Scoping to local.name keeps
      # the stack self-contained.
      family = local.name

      container_definitions = {
        # PgBouncer sidecar — runs in the same task network namespace as the app.
        # The app's DATABASE_URL points to localhost:5432 (pgbouncer), not RDS directly.
        # transaction mode: server connections are returned to the pool after each
        # transaction, multiplexing many app connections onto a small RDS pool.
        # pgbouncer connects to RDS using the secret injected via DB_HOST / DB_PORT /
        # DB_NAME / DB_USER / DB_PASSWORD environment variables.
        pgbouncer = {
          # Built from edoburu/pgbouncer:v1.25.1-p0 with Alpine security updates,
          # then pushed to ECR by CI to avoid Docker Hub pull rate limits.
          image     = "${module.ecr_pgbouncer.repository_url}:v1.25.1-p0"
          essential = true

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
          # Explicit name keeps the log group stack-scoped and readable instead of
          # relying on the module's generic service-key-derived default.
          cloudwatch_log_group_name = "/ecs/${local.name}/pgbouncer"
        }

        app = {
          # var.initial_image_tag is used only on the first apply (bootstrap).
          # ignore_task_definition_changes = true on the service means Terraform
          # never registers a new revision after that — CI owns the image tag.
          image     = "${module.ecr_app.repository_url}:${var.initial_image_tag}"
          essential = true

          # ECS container definition keys are camelCase — they map directly to the ECS API
          portMappings = [{ containerPort = 8000, protocol = "tcp" }]

          # ECS does not interpolate $(VAR) in environment values. DB_PASSWORD is
          # injected as a secret; the app's config.py composes DATABASE_URL at startup.
          secrets = [
            { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
          ]

          environment = [
            { name = "ORDER_EVENTS_QUEUE_URL", value = aws_sqs_queue.order_events.url },
          ]

          # pgbouncer must be accepting connections before the app starts.
          dependsOn = [{ containerName = "pgbouncer", condition = "START" }]

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
          # Explicit name keeps the log group stack-scoped and readable instead of
          # relying on the module's generic service-key-derived default.
          cloudwatch_log_group_name = "/ecs/${local.name}/app"
        }
      }

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

      service_registries = var.enable_observability_stack ? {
        registry_arn   = aws_service_discovery_service.app[0].arn
        container_name = "app"
        container_port = 8000
      } : null
    }
  }

  tags = local.tags
}

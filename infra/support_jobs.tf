################################################################################
# Support workloads
#
# These one-off operational tasks stay deployed in this phase, but they are
# separated from the lean base service path so the platform boundary is easier
# to understand.
################################################################################

################################################################################
# ECR — support workload images
################################################################################

module "ecr_liquibase" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 3.0"

  repository_name                 = "${local.name}/liquibase"
  repository_image_tag_mutability = "IMMUTABLE"
  repository_image_scan_on_push   = true

  repository_read_write_access_arns = [aws_iam_role.github_actions.arn]

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

module "ecr_worker" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 3.0"

  repository_name                 = "${local.name}/worker"
  repository_image_tag_mutability = "IMMUTABLE"
  repository_image_scan_on_push   = true

  repository_read_write_access_arns = [aws_iam_role.github_actions.arn]

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
# Worker task definition — one-off Fargate task triggered by CI for backfill.
# Connects directly to RDS (not via pgbouncer) — backfill transactions are
# long-running and incompatible with pgbouncer's transaction-mode pool.
# Reuses the execution role and task role from the app service.
################################################################################

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = module.ecs.services["app"].tasks_iam_role_arn

  container_definitions = jsonencode([
    {
      name = "worker"
      # var.initial_image_tag is used only on the first apply (bootstrap).
      # CI always calls render-task-definition + register-task-definition
      # with the real SHA before running this one-off task — Terraform's
      # registered revision is never used directly after bootstrap.
      image     = "${module.ecr_worker.repository_url}:${var.initial_image_tag}"
      essential = true
      secrets = [
        # ECS does not interpolate $(VAR) in environment values. DB_PASSWORD is
        # injected as a secret; worker's config.py composes BACKFILL_DATABASE_URL at startup.
        { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
      ]
      environment = [
        { name = "DB_HOST", value = module.rds.db_instance_address },
        { name = "DB_PORT", value = tostring(module.rds.db_instance_port) },
        { name = "BACKFILL_BATCH_SIZE", value = tostring(var.backfill_batch_size) },
        { name = "BACKFILL_SLEEP_MS", value = "100" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${local.name}/worker"
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name}/worker"
  retention_in_days = 14
  tags              = local.tags
}

################################################################################
# Liquibase task definition — one-off Fargate task for schema migrations.
# Uses a custom image built FROM liquibase/liquibase:4.33.0 with the db/changelog/
# directory baked in (see db/Dockerfile). The app image stays free of Liquibase
# and its JVM dependency.
# Connects directly to RDS (not pgbouncer) — DDL requires a session connection.
################################################################################

resource "aws_ecs_task_definition" "liquibase" {
  family                   = "${local.name}-liquibase"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  # 512 CPU / 1024 MiB is the minimum Fargate size that comfortably runs the
  # Liquibase JVM without OOM on startup.
  cpu    = 512
  memory = 1024

  execution_role_arn = aws_iam_role.task_exec.arn
  # No task role needed — Liquibase only talks to RDS, not AWS APIs.

  container_definitions = jsonencode([
    {
      name = "liquibase"
      # Changelogs are baked into this image at build time (see db/Dockerfile).
      # var.initial_image_tag is used only on the first apply (bootstrap).
      # CI always calls render-task-definition + register-task-definition
      # with the real SHA before running this one-off task — Terraform's
      # registered revision is never used directly after bootstrap.
      image     = "${module.ecr_liquibase.repository_url}:${var.initial_image_tag}"
      essential = true

      secrets = [
        # RDS-managed secret only has username + password. Host/port/dbname are static.
        # Injected directly as the Liquibase env vars — ECS $(VAR) interpolation only
        # works in command/entryPoint, not in environment values.
        { name = "LIQUIBASE_COMMAND_USERNAME", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:username::" },
        { name = "LIQUIBASE_COMMAND_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
      ]

      environment = [
        { name = "LIQUIBASE_COMMAND_URL", value = "jdbc:postgresql://${module.rds.db_instance_address}:${module.rds.db_instance_port}/aws_sdlc_containers" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${local.name}/liquibase"
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "liquibase"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "liquibase" {
  name              = "/ecs/${local.name}/liquibase"
  retention_in_days = 14
  tags              = local.tags
}

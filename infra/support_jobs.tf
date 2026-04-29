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

module "ecr_data_export_job" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 3.0"

  repository_name                 = "${local.name}/data-export-job"
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
# Data export job — scheduled Fargate task that writes order_contact_email
# exports to the data hub S3 bucket. The scheduler targets the task definition
# family so CI-registered revisions become active without a Terraform apply.
################################################################################

resource "aws_iam_role" "data_export_job" {
  name               = "${local.name}-data-export-job"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "data_export_job_s3" {
  statement {
    sid     = "WriteDataHubObjects"
    actions = ["s3:PutObject"]
    resources = [
      "${aws_s3_bucket.data_hub.arn}/raw/*",
      "${aws_s3_bucket.data_hub.arn}/manifests/*",
    ]
  }
}

resource "aws_iam_role_policy" "data_export_job_s3" {
  name   = "data-hub-write"
  role   = aws_iam_role.data_export_job.id
  policy = data.aws_iam_policy_document.data_export_job_s3.json
}

resource "aws_ecs_task_definition" "data_export_job" {
  family                   = "${local.name}-data-export-job"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.data_export_job_cpu
  memory                   = var.data_export_job_memory
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.data_export_job.arn

  container_definitions = jsonencode([
    {
      name = "data-export-job"
      # var.initial_image_tag is used only on the first apply (bootstrap).
      # CI registers a SHA-tagged revision before the scheduler uses the task
      # family for recurring exports.
      image     = "${module.ecr_data_export_job.repository_url}:${var.initial_image_tag}"
      essential = true
      secrets = [
        { name = "DB_USER", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
      ]
      environment = [
        { name = "DB_HOST", value = module.rds.db_instance_address },
        { name = "DB_PORT", value = tostring(module.rds.db_instance_port) },
        { name = "DB_NAME", value = "aws_sdlc_containers" },
        { name = "DATA_EXPORT_OUTPUT_DIR", value = "/tmp/aws-sdlc-containers-data-hub" },
        { name = "DATA_EXPORT_S3_BUCKET", value = aws_s3_bucket.data_hub.bucket },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${local.name}/data-export-job"
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "data-export-job"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "data_export_job" {
  name              = "/ecs/${local.name}/data-export-job"
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_cloudwatch_log_metric_filter" "data_export_success" {
  name           = "${local.name}-data-export-success"
  log_group_name = aws_cloudwatch_log_group.data_export_job.name
  pattern        = "{ ($.dataset = \"order_contact_email\") && ($.status = \"succeeded\") }"

  metric_transformation {
    name      = "SuccessCount"
    namespace = "${local.name}/DataExport"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "data_export_success_missing" {
  alarm_name          = "${local.name}-data-export-success-missing"
  alarm_description   = "No successful data export manifest was observed for two daily evaluation windows. Runbook: ops/runbooks/data-export-job-failure.md"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 1
  metric_name         = "SuccessCount"
  namespace           = "${local.name}/DataExport"
  period              = 86400
  statistic           = "Sum"
  treat_missing_data  = "breaching"
  unit                = "Count"

  tags = local.tags
}

data "aws_iam_policy_document" "data_export_scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "data_export_scheduler" {
  name               = "${local.name}-data-export-scheduler"
  assume_role_policy = data.aws_iam_policy_document.data_export_scheduler_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "data_export_scheduler" {
  statement {
    sid       = "RunDataExportTask"
    actions   = ["ecs:RunTask"]
    resources = ["arn:aws:ecs:${local.region}:${local.account_id}:task-definition/${local.name}-data-export-job:*"]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [module.ecs.cluster_arn]
    }
  }

  statement {
    sid     = "PassDataExportRoles"
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.task_exec.arn,
      aws_iam_role.data_export_job.arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "data_export_scheduler" {
  name   = "run-data-export"
  role   = aws_iam_role.data_export_scheduler.id
  policy = data.aws_iam_policy_document.data_export_scheduler.json
}

resource "aws_scheduler_schedule" "data_export_job" {
  name                = "${local.name}-data-export-job"
  schedule_expression = var.data_export_schedule_expression

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = module.ecs.cluster_arn
    role_arn = aws_iam_role.data_export_scheduler.arn

    ecs_parameters {
      # Omitting the revision intentionally selects the latest ACTIVE revision.
      task_definition_arn = aws_ecs_task_definition.data_export_job.arn_without_revision
      launch_type         = "FARGATE"
      platform_version    = "LATEST"

      network_configuration {
        assign_public_ip = false
        security_groups  = [aws_security_group.app.id]
        subnets          = module.vpc.private_subnets
      }
    }

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "data_export_scheduler_target_errors" {
  alarm_name          = "${local.name}-data-export-scheduler-target-errors"
  alarm_description   = "EventBridge Scheduler target delivery failed for the data export schedule group. Runbook: ops/runbooks/data-export-job-failure.md"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  threshold           = 0
  metric_name         = "TargetErrorCount"
  namespace           = "AWS/Scheduler"
  period              = 300
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  unit                = "Count"

  # EventBridge Scheduler publishes this metric by schedule group, not schedule
  # name. This stack currently owns one schedule in the default group.
  dimensions = {
    ScheduleGroup = "default"
  }

  tags = local.tags
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

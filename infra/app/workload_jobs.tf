################################################################################
# Support workloads
#
# These one-off operational tasks stay deployed in this phase, but they are
# separated from the lean base service path so the platform boundary is easier
# to understand.
################################################################################

locals {
  support_task_definition_defaults = {
    requires_compatibilities = ["FARGATE"]
    network_mode             = "awsvpc"
    execution_role_arn       = aws_iam_role.task_exec.arn
  }

  support_workload_log_group_defaults = {
    kms_key_id        = aws_kms_key.cloudwatch_logs.arn
    retention_in_days = 14
    tags              = local.tags
  }

  job_workloads = {
    for name, workload in local.workloads_by_name :
    name => workload
    if workload.kind == "job"
  }

  support_job_runtime_overrides = {
    backfill_worker = {
      cpu           = var.backfill_worker_cpu
      memory        = var.backfill_worker_memory
      task_role_arn = aws_iam_role.primary_edge_task_deploy.arn
    }
    data_export_job = {
      cpu           = var.data_export_job_cpu
      memory        = var.data_export_job_memory
      task_role_arn = aws_iam_role.data_export_job.arn
    }
  }

  support_job_workloads = {
    for name, workload in local.job_workloads :
    name => {
      family         = "${local.name}-${workload.image.repository}"
      repository     = workload.image.repository
      container_name = workload.image.repository
      cpu            = local.support_job_runtime_overrides[name].cpu
      memory         = local.support_job_runtime_overrides[name].memory
      task_role_arn  = local.support_job_runtime_overrides[name].task_role_arn
    }
    if contains(keys(local.support_job_runtime_overrides), name)
  }

  scheduled_support_job_workloads = {
    for name, workload in local.support_job_workloads :
    name => workload
    if local.workload_capabilities[name].scheduled_execution
  }

  scheduled_job_schedule_expressions = {
    data_export_job = var.data_export_schedule_expression
  }

  scheduled_job_target_error_alarm_description = "EventBridge Scheduler target delivery failed for a scheduled support workload in the default schedule group."

  scheduled_job_target_error_alarm_name = "${local.name}-scheduled-job-scheduler-target-errors"
  scheduled_job_target_error_dimensions = {
    ScheduleGroup = "default"
  }

  scheduled_job_success_alarm_workloads = {
    data_export_job = {
      alarm_enabled = var.enable_data_export_success_cloudwatch_alarm
    }
  }

  liquibase_log_group_name = "/ecs/${local.name}/liquibase"

  async_eventing_runtime_files = {
    "components/async-events-pubsub.yaml" = aws_s3_object.async_eventing_dapr_component.key
    "components/resiliency.yaml"          = aws_s3_object.async_eventing_dapr_resiliency.key
    "config/config.yaml"                  = aws_s3_object.async_eventing_dapr_config.key
  }

  async_eventing_dapr_config_volume_name = "dapr-config"
  async_eventing_dapr_mount_path         = "/dapr"
  async_eventing_dapr_loader_dependency = [
    { containerName = "dapr-config-loader", condition = "SUCCESS" },
  ]
  async_eventing_dapr_writable_mount_points = [
    {
      sourceVolume  = local.async_eventing_dapr_config_volume_name
      containerPath = local.async_eventing_dapr_mount_path
      readOnly      = false
    },
  ]
  async_eventing_dapr_readonly_mount_points = [
    {
      sourceVolume  = local.async_eventing_dapr_config_volume_name
      containerPath = local.async_eventing_dapr_mount_path
      readOnly      = true
    },
  ]

  async_eventing_dapr_config_loader_command = join(
    " && ",
    concat(
      [
        "mkdir -p ${local.async_eventing_dapr_mount_path}/components ${local.async_eventing_dapr_mount_path}/config"
      ],
      [
        for target_path, source_key in local.async_eventing_runtime_files :
        "aws s3 cp s3://${aws_s3_bucket.runtime_config.bucket}/${source_key} ${local.async_eventing_dapr_mount_path}/${target_path}"
      ]
    )
  )

  primary_async_eventing_dapr_app_id = local.primary_async_eventing_dapr.app_id

  primary_async_eventing_daprd_command = [
    "./daprd",
    "--app-id",
    local.primary_async_eventing_dapr_app_id,
    "--app-port",
    tostring(local.primary_async_eventing_service_port),
    "--dapr-http-port",
    "3500",
    "--components-path",
    "${local.async_eventing_dapr_mount_path}/components",
    "--config",
    "${local.async_eventing_dapr_mount_path}/config/config.yaml",
  ]

  primary_async_eventing_port_mappings = [
    {
      containerPort = local.primary_async_eventing_service_port
      hostPort      = local.primary_async_eventing_service_port
      protocol      = "tcp"
    },
  ]

  primary_async_eventing_health_check = {
    command = [
      "CMD-SHELL",
      "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${local.primary_async_eventing_service_port}/health')\"",
    ]
    interval    = 10
    timeout     = 3
    retries     = 3
    startPeriod = 20
  }
}

################################################################################
# Worker task definition — one-off Fargate task triggered by CI for backfill.
# Connects directly to RDS (not via pgbouncer) — backfill transactions are
# long-running and incompatible with pgbouncer's transaction-mode pool.
# Reuses the shared execution role and app task role.
################################################################################

resource "aws_ecs_task_definition" "support_job" {
  for_each = local.support_job_workloads

  family                   = each.value.family
  requires_compatibilities = local.support_task_definition_defaults.requires_compatibilities
  network_mode             = local.support_task_definition_defaults.network_mode
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = local.support_task_definition_defaults.execution_role_arn
  task_role_arn            = each.value.task_role_arn

  container_definitions = jsonencode([
    merge(local.ecs_container_defaults, {
      name = each.value.container_name
      # var.bootstrap_image_tag is used only on the first apply (bootstrap).
      # CI always registers a SHA-tagged revision before running or scheduling
      # these support jobs, so Terraform's bootstrap revision is only a seed.
      image            = format("%s:%s", module.ecr[each.key].repository_url, var.bootstrap_image_tag)
      essential        = true
      secrets          = local.workload_secrets[each.key]
      environment      = local.workload_environment[each.key]
      logConfiguration = local.workload_log_configuration[each.key]
    })
  ])

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "support_job" {
  for_each = local.support_job_workloads

  name              = local.workload_log_group_names[each.key]
  kms_key_id        = local.support_workload_log_group_defaults.kms_key_id
  retention_in_days = local.support_workload_log_group_defaults.retention_in_days
  tags              = local.support_workload_log_group_defaults.tags
}

################################################################################
# Data export job — scheduled Fargate task that exports workload-owned data to
# the data hub S3 bucket. The scheduler targets the task definition family so
# CI-registered revisions become active without a Terraform apply.
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

resource "aws_cloudwatch_log_metric_filter" "data_export_success" {
  count = var.enable_data_export_success_cloudwatch_alarm ? 1 : 0

  name           = "${local.name}-data-export-success"
  log_group_name = aws_cloudwatch_log_group.support_job["data_export_job"].name
  pattern        = "{ ($.log = *event*) && ($.log = *data_export_succeeded*) && ($.log = *status*) && ($.log = *succeeded*) }"

  metric_transformation {
    name      = "SuccessCount"
    namespace = "${local.name}/DataExport"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "data_export_success_missing" {
  count = local.scheduled_job_success_alarm_workloads["data_export_job"].alarm_enabled ? 1 : 0

  alarm_name          = "${local.name}-data-export-success-missing"
  alarm_description   = "No successful data export manifest was observed for two daily evaluation windows. Runbook: docs/runbooks/data-export-job-failure.md"
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

resource "aws_iam_role" "scheduled_job_scheduler" {
  for_each = local.scheduled_support_job_workloads

  name               = "${each.value.family}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.data_export_scheduler_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "scheduled_job_scheduler" {
  for_each = local.scheduled_support_job_workloads

  statement {
    sid       = "RunScheduledJobTask"
    actions   = ["ecs:RunTask"]
    resources = ["arn:aws:ecs:${local.region}:${local.account_id}:task-definition/${each.value.family}:*"]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [module.ecs.cluster_arn]
    }
  }

  statement {
    sid     = "PassScheduledJobRoles"
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.task_exec.arn,
      each.value.task_role_arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "scheduled_job_scheduler" {
  for_each = local.scheduled_support_job_workloads

  name   = "run-${each.value.repository}"
  role   = aws_iam_role.scheduled_job_scheduler[each.key].id
  policy = data.aws_iam_policy_document.scheduled_job_scheduler[each.key].json
}

resource "aws_scheduler_schedule" "scheduled_job" {
  for_each = local.scheduled_support_job_workloads

  name                = each.value.family
  schedule_expression = local.scheduled_job_schedule_expressions[each.key]

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = module.ecs.cluster_arn
    role_arn = aws_iam_role.scheduled_job_scheduler[each.key].arn

    ecs_parameters {
      # Omitting the revision intentionally selects the latest ACTIVE revision.
      task_definition_arn = aws_ecs_task_definition.support_job[each.key].arn_without_revision
      launch_type         = "FARGATE"
      platform_version    = "LATEST"

      network_configuration {
        assign_public_ip = false
        security_groups  = [aws_security_group.primary_edge.id]
        subnets          = local.platform.private_subnet_ids
      }
    }

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "scheduled_job_scheduler_target_errors" {
  alarm_name          = local.scheduled_job_target_error_alarm_name
  alarm_description   = local.scheduled_job_target_error_alarm_description
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
  # name. Keep one group-level alarm even if multiple scheduled workloads exist.
  dimensions = local.scheduled_job_target_error_dimensions

  tags = local.tags
}

################################################################################
# Event consumer — one small async runtime that relays durable outbox messages
# through Dapr pub/sub and records consumed deliveries into an idempotent
# receipt table.
################################################################################

resource "aws_iam_role" "event_consumer" {
  name               = "${local.name}-event-consumer"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "event_consumer_sqs" {
  statement {
    sid = "PublishAndConsumeDaprAsyncEvents"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
      "sns:GetTopicAttributes",
      "sns:ListSubscriptionsByTopic",
      "sns:Publish",
    ]
    resources = [
      aws_sns_topic.async_eventing.arn,
      aws_sqs_queue.async_eventing.arn,
    ]
  }

  statement {
    sid       = "ReadDaprRuntimeConfig"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.runtime_config.arn}/${local.primary_async_eventing_dapr_config_prefix}/*"]
  }

  statement {
    sid = "UseAsyncEventingSnsKms"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.async_eventing_sns.arn]

    condition {
      test     = "StringEquals"
      variable = "kms:CallerAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["sns.${local.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "event_consumer_sqs" {
  name   = "async-events-relay-consume"
  role   = aws_iam_role.event_consumer.id
  policy = data.aws_iam_policy_document.event_consumer_sqs.json
}

resource "aws_ecs_task_definition" "event_consumer" {
  family                   = "${local.name}-event-consumer"
  requires_compatibilities = local.support_task_definition_defaults.requires_compatibilities
  network_mode             = local.support_task_definition_defaults.network_mode
  cpu                      = var.event_consumer_cpu
  memory                   = var.event_consumer_memory
  execution_role_arn       = local.support_task_definition_defaults.execution_role_arn
  task_role_arn            = aws_iam_role.event_consumer.arn

  volume {
    name = local.async_eventing_dapr_config_volume_name
  }

  container_definitions = jsonencode([
    merge(local.ecs_container_defaults, {
      name      = "dapr-config-loader"
      image     = var.runtime_config_loader_image
      essential = false
      # The AWS CLI image ships with an `aws` entrypoint. Override it so ECS
      # runs the copy script via a shell instead of attempting `aws sh -c ...`.
      entryPoint = ["/bin/sh", "-c"]
      environment = [
        { name = "AWS_REGION", value = local.region },
        { name = "AWS_DEFAULT_REGION", value = local.region },
      ]
      command          = [local.async_eventing_dapr_config_loader_command]
      mountPoints      = local.async_eventing_dapr_writable_mount_points
      logConfiguration = local.sidecar_log_configuration["dapr_config_loader"]
    }),
    merge(local.ecs_container_defaults, {
      name             = "daprd"
      image            = var.dapr_image
      essential        = true
      environment      = [{ name = "AWS_REGION", value = local.region }]
      command          = local.primary_async_eventing_daprd_command
      mountPoints      = local.async_eventing_dapr_readonly_mount_points
      dependsOn        = local.async_eventing_dapr_loader_dependency
      logConfiguration = local.sidecar_log_configuration["daprd"]
    }),
    merge(local.ecs_container_defaults, {
      name             = "event-consumer"
      image            = format("%s:%s", module.ecr["event_consumer"].repository_url, var.bootstrap_image_tag)
      essential        = true
      portMappings     = local.primary_async_eventing_port_mappings
      secrets          = local.workload_secrets["event_consumer"]
      environment      = local.workload_environment["event_consumer"]
      dependsOn        = local.async_eventing_dapr_loader_dependency
      healthCheck      = local.primary_async_eventing_health_check
      logConfiguration = local.workload_log_configuration["event_consumer"]
    })
  ])

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "event_consumer" {
  name              = local.workload_log_group_names["event_consumer"]
  kms_key_id        = local.support_workload_log_group_defaults.kms_key_id
  retention_in_days = local.support_workload_log_group_defaults.retention_in_days
  tags              = local.support_workload_log_group_defaults.tags
}

resource "aws_ecs_service" "event_consumer" {
  name            = "event-consumer"
  cluster         = module.ecs.cluster_arn
  task_definition = aws_ecs_task_definition.event_consumer.arn
  desired_count   = var.event_consumer_bootstrap_desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
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
# Liquibase task definition — one-off Fargate task for schema migrations.
# Uses a custom image built FROM liquibase/liquibase:5.0.2 with the db/changelog/
# directory baked in (see db/Dockerfile). The app image stays free of Liquibase
# and its JVM dependency.
# Connects directly to RDS (not pgbouncer) — DDL requires a session connection.
################################################################################

resource "aws_iam_role" "liquibase" {
  name               = "${local.name}-liquibase"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

resource "aws_ecs_task_definition" "liquibase" {
  family                   = "${local.name}-liquibase"
  requires_compatibilities = local.support_task_definition_defaults.requires_compatibilities
  network_mode             = local.support_task_definition_defaults.network_mode
  # 512 CPU / 1024 MiB is the minimum Fargate size that comfortably runs the
  # Liquibase JVM without OOM on startup.
  cpu    = 512
  memory = 1024

  execution_role_arn = local.support_task_definition_defaults.execution_role_arn
  task_role_arn      = aws_iam_role.liquibase.arn

  container_definitions = jsonencode([
    merge(local.ecs_container_defaults, {
      name = "liquibase"
      # Changelogs are baked into this image at build time (see db/Dockerfile).
      # var.bootstrap_image_tag is used only on the first apply (bootstrap).
      # CI always calls render-task-definition + register-task-definition
      # with the real SHA before running this one-off task — Terraform's
      # registered revision is never used directly after bootstrap.
      image            = format("%s:%s", module.ecr["liquibase"].repository_url, var.bootstrap_image_tag)
      essential        = true
      workingDirectory = "/liquibase"
      command = [
        "--search-path=/liquibase",
        "--changelog-file=changelog/db.changelog-master.yaml",
        "update",
      ]

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
          "awslogs-group"         = local.liquibase_log_group_name
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "liquibase"
        }
      }
    })
  ])

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "liquibase" {
  name              = local.liquibase_log_group_name
  kms_key_id        = local.support_workload_log_group_defaults.kms_key_id
  retention_in_days = local.support_workload_log_group_defaults.retention_in_days
  tags              = local.support_workload_log_group_defaults.tags
}

################################################################################
# Optional observability stack — ECS Grafana, Loki, and Prometheus
#
# Disabled by default. This is the first deployed Grafana-stack slice and keeps
# CloudWatch app/platform logs and alarms untouched.
################################################################################

locals {
  observability_bucket_name   = "${local.name}-observability-${local.account_id}"
  observability_config_prefix = "config"
  observability_dns_namespace = "${local.name}.local"
  grafana_admin_secret_arn    = var.enable_observability_stack ? data.aws_secretsmanager_secret.grafana_admin[0].arn : null
  firelens_image              = "${module.ecr_firelens.repository_url}:${var.firelens_image_tag}"
  firelens_loki_host          = "loki.${local.observability_dns_namespace}"
  ecs_container_defaults = {
    environment    = []
    mountPoints    = []
    portMappings   = []
    systemControls = []
    volumesFrom    = []
  }
  firelens_log_configuration = {
    logDriver = "awsfirelens"
    options = {
      "log-driver-buffer-limit" = "2097152"
    }
  }
  firelens_environment = [
    { name = "AWS_REGION", value = local.region },
    { name = "STACK_NAME", value = local.name },
    { name = "ENVIRONMENT", value = "aws" },
    { name = "LOKI_HOST", value = local.firelens_loki_host },
    { name = "LOKI_PORT", value = "3100" },
  ]
  firelens_router_container = var.enable_observability_stack ? [{
    name           = "log-router"
    image          = local.firelens_image
    essential      = true
    user           = "0"
    mountPoints    = []
    portMappings   = []
    systemControls = []
    volumesFrom    = []
    firelensConfiguration = {
      type = "fluentbit"
      options = {
        "config-file-type"        = "file"
        "config-file-value"       = "/fluent-bit/configs/aws-sdlc-dual-output.conf"
        "enable-ecs-log-metadata" = "true"
      }
    }
    environment = local.firelens_environment
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.firelens[0].name
        "awslogs-region"        = local.region
        "awslogs-stream-prefix" = "firelens"
      }
    }
  }] : []
}

data "aws_secretsmanager_secret" "grafana_admin" {
  count = var.enable_observability_stack ? 1 : 0
  name  = var.grafana_admin_secret_name
}

################################################################################
# S3 — Loki storage and deployed config objects
################################################################################

resource "aws_s3_bucket" "observability" {
  #checkov:skip=CKV_AWS_18:Access logs would add unrelated storage/cost for this opt-in sandbox observability bucket.
  #checkov:skip=CKV_AWS_144:Cross-region replication is production recovery overhead, not needed for this lean opt-in slice.
  #checkov:skip=CKV_AWS_145:S3-managed AES256 encryption is sufficient here; KMS adds cost and key operations for no sandbox value.
  #checkov:skip=CKV2_AWS_62:No event consumer exists for observability bucket notifications.
  count  = var.enable_observability_stack ? 1 : 0
  bucket = local.observability_bucket_name

  tags = merge(local.tags, {
    Purpose = "observability"
  })
}

resource "aws_s3_bucket_public_access_block" "observability" {
  count  = var.enable_observability_stack ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "observability" {
  count  = var.enable_observability_stack ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

data "aws_iam_policy_document" "observability_alb_access_logs" {
  count = var.enable_observability_stack ? 1 : 0

  statement {
    sid = "AllowAlbAccessLogs"

    principals {
      type        = "Service"
      identifiers = ["logdelivery.elasticloadbalancing.amazonaws.com"]
    }

    actions = ["s3:PutObject"]

    resources = [
      "${aws_s3_bucket.observability[0].arn}/alb-access-logs/AWSLogs/${local.account_id}/*",
    ]
  }
}

resource "aws_s3_bucket_policy" "observability_alb_access_logs" {
  count  = var.enable_observability_stack ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id
  policy = data.aws_iam_policy_document.observability_alb_access_logs[0].json
}

resource "aws_s3_bucket_server_side_encryption_configuration" "observability" {
  count  = var.enable_observability_stack ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "observability" {
  count  = var.enable_observability_stack ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "observability" {
  count  = var.enable_observability_stack ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id

  rule {
    id     = "expire-noncurrent-observability-versions"
    status = "Enabled"

    filter {
      prefix = ""
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.observability]
}

resource "aws_s3_object" "loki_config" {
  count        = var.enable_observability_stack ? 1 : 0
  bucket       = aws_s3_bucket.observability[0].id
  key          = "${local.observability_config_prefix}/loki/loki.yml"
  content_type = "text/yaml"
  content = templatefile("${path.module}/templates/observability/loki.yml.tftpl", {
    aws_region  = local.region
    bucket_name = aws_s3_bucket.observability[0].bucket
  })
}

resource "aws_s3_object" "prometheus_config" {
  count        = var.enable_observability_stack ? 1 : 0
  bucket       = aws_s3_bucket.observability[0].id
  key          = "${local.observability_config_prefix}/prometheus/prometheus.yml"
  content_type = "text/yaml"
  content = templatefile("${path.module}/templates/observability/prometheus.yml.tftpl", {
    dns_namespace = local.observability_dns_namespace
  })
}

resource "aws_s3_object" "tempo_config" {
  count        = var.enable_observability_stack ? 1 : 0
  bucket       = aws_s3_bucket.observability[0].id
  key          = "${local.observability_config_prefix}/tempo/tempo.yml"
  content_type = "text/yaml"
  content = templatefile("${path.module}/templates/observability/tempo.yml.tftpl", {
    aws_region  = local.region
    bucket_name = aws_s3_bucket.observability[0].bucket
  })
}

resource "aws_s3_object" "prometheus_app_alerts" {
  count        = var.enable_observability_stack ? 1 : 0
  bucket       = aws_s3_bucket.observability[0].id
  key          = "${local.observability_config_prefix}/prometheus/rules/app-alerts.yml"
  content_type = "text/yaml"
  source       = "${path.module}/../../observability/prometheus/rules/app-alerts.yml"
  source_hash  = filemd5("${path.module}/../../observability/prometheus/rules/app-alerts.yml")
}

resource "aws_s3_object" "grafana_datasources" {
  count        = var.enable_observability_stack ? 1 : 0
  bucket       = aws_s3_bucket.observability[0].id
  key          = "${local.observability_config_prefix}/grafana/provisioning/datasources/datasources.yml"
  content_type = "text/yaml"
  source       = "${path.module}/../../observability/grafana/provisioning/datasources/datasources.yml"
  source_hash  = filemd5("${path.module}/../../observability/grafana/provisioning/datasources/datasources.yml")
}

resource "aws_s3_object" "grafana_dashboards_provisioning" {
  count        = var.enable_observability_stack ? 1 : 0
  bucket       = aws_s3_bucket.observability[0].id
  key          = "${local.observability_config_prefix}/grafana/provisioning/dashboards/dashboards.yml"
  content_type = "text/yaml"
  source       = "${path.module}/../../observability/grafana/provisioning/dashboards/dashboards.yml"
  source_hash  = filemd5("${path.module}/../../observability/grafana/provisioning/dashboards/dashboards.yml")
}

resource "aws_s3_object" "grafana_app_dashboard" {
  count        = var.enable_observability_stack ? 1 : 0
  bucket       = aws_s3_bucket.observability[0].id
  key          = "${local.observability_config_prefix}/grafana/dashboards/app-overview.json"
  content_type = "application/json"
  source       = "${path.module}/../../observability/grafana/dashboards/app-overview.json"
  source_hash  = filemd5("${path.module}/../../observability/grafana/dashboards/app-overview.json")
}

resource "aws_s3_object" "grafana_log_groups_dashboard" {
  count        = var.enable_observability_stack ? 1 : 0
  bucket       = aws_s3_bucket.observability[0].id
  key          = "${local.observability_config_prefix}/grafana/dashboards/log-groups.json"
  content_type = "application/json"
  source       = "${path.module}/../../observability/grafana/dashboards/log-groups.json"
  source_hash  = filemd5("${path.module}/../../observability/grafana/dashboards/log-groups.json")
}

################################################################################
# IAM
################################################################################

resource "aws_iam_role" "observability_task_exec" {
  count              = var.enable_observability_stack ? 1 : 0
  name               = "${local.name}-observability-task-exec"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "observability_task_exec_managed" {
  count      = var.enable_observability_stack ? 1 : 0
  role       = aws_iam_role.observability_task_exec[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "observability_task_exec_grafana_secret" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "grafana-admin-secret-access"
  role  = aws_iam_role.observability_task_exec[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadGrafanaAdminSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = local.grafana_admin_secret_arn
      }
    ]
  })
}

resource "aws_iam_role" "loki" {
  count              = var.enable_observability_stack ? 1 : 0
  name               = "${local.name}-loki"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

resource "aws_iam_role" "prometheus" {
  count              = var.enable_observability_stack ? 1 : 0
  name               = "${local.name}-prometheus"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

resource "aws_iam_role" "grafana" {
  count              = var.enable_observability_stack ? 1 : 0
  name               = "${local.name}-grafana"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

resource "aws_iam_role" "tempo" {
  count              = var.enable_observability_stack ? 1 : 0
  name               = "${local.name}-tempo"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy" "loki_s3" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "loki-s3-storage-and-config"
  role  = aws_iam_role.loki[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListObservabilityBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.observability[0].arn
      },
      {
        Sid    = "ReadConfig"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "${aws_s3_bucket.observability[0].arn}/${local.observability_config_prefix}/*",
        ]
      },
      {
        Sid    = "ReadWriteLokiObjects"
        Effect = "Allow"
        Action = [
          "s3:DeleteObject",
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = "${aws_s3_bucket.observability[0].arn}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "tempo_s3" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "tempo-s3-storage-and-config"
  role  = aws_iam_role.tempo[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListObservabilityBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.observability[0].arn
      },
      {
        Sid    = "ReadConfig"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "${aws_s3_bucket.observability[0].arn}/${local.observability_config_prefix}/*",
        ]
      },
      {
        Sid    = "ReadWriteTempoObjects"
        Effect = "Allow"
        Action = [
          "s3:DeleteObject",
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = "${aws_s3_bucket.observability[0].arn}/tempo/*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "prometheus_config_read" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "observability-config-read"
  role  = aws_iam_role.prometheus[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadConfig"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.observability[0].arn}/${local.observability_config_prefix}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "loki_firelens_cloudwatch_logs" {
  count      = var.enable_observability_stack ? 1 : 0
  role       = aws_iam_role.loki[0].name
  policy_arn = aws_iam_policy.firelens_cloudwatch_logs.arn
}

resource "aws_iam_role_policy_attachment" "prometheus_firelens_cloudwatch_logs" {
  count      = var.enable_observability_stack ? 1 : 0
  role       = aws_iam_role.prometheus[0].name
  policy_arn = aws_iam_policy.firelens_cloudwatch_logs.arn
}

resource "aws_iam_role_policy_attachment" "grafana_firelens_cloudwatch_logs" {
  count      = var.enable_observability_stack ? 1 : 0
  role       = aws_iam_role.grafana[0].name
  policy_arn = aws_iam_policy.firelens_cloudwatch_logs.arn
}

resource "aws_iam_role_policy_attachment" "tempo_firelens_cloudwatch_logs" {
  count      = var.enable_observability_stack ? 1 : 0
  role       = aws_iam_role.tempo[0].name
  policy_arn = aws_iam_policy.firelens_cloudwatch_logs.arn
}

resource "aws_iam_role_policy" "grafana_config_read" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "observability-config-read"
  role  = aws_iam_role.grafana[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadConfig"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.observability[0].arn}/${local.observability_config_prefix}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "grafana_ssm_exec" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "ssm-exec"
  role  = aws_iam_role.grafana[0].id
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

resource "aws_iam_role_policy" "loki_ssm_exec" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "ssm-exec"
  role  = aws_iam_role.loki[0].id
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

################################################################################
# Networking and service discovery
################################################################################

resource "aws_service_discovery_private_dns_namespace" "observability" {
  count       = var.enable_observability_stack ? 1 : 0
  name        = local.observability_dns_namespace
  description = "Private service discovery for ${local.name} observability"
  vpc         = local.platform.vpc_id
  tags        = local.tags
}

resource "aws_service_discovery_service" "app" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "app"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.observability[0].id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {}

  lifecycle {
    ignore_changes = [health_check_custom_config]
  }

  tags = local.tags
}

resource "aws_service_discovery_service" "loki" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "loki"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.observability[0].id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {}

  lifecycle {
    ignore_changes = [health_check_custom_config]
  }

  tags = local.tags
}

resource "aws_service_discovery_service" "prometheus" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "prometheus"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.observability[0].id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {}

  lifecycle {
    ignore_changes = [health_check_custom_config]
  }

  tags = local.tags
}

resource "aws_service_discovery_service" "grafana" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "grafana"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.observability[0].id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {}

  lifecycle {
    ignore_changes = [health_check_custom_config]
  }

  tags = local.tags
}

resource "aws_service_discovery_service" "tempo" {
  count = var.enable_observability_stack ? 1 : 0
  name  = "tempo"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.observability[0].id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {}

  lifecycle {
    ignore_changes = [health_check_custom_config]
  }

  tags = local.tags
}

resource "aws_security_group" "observability" {
  count       = var.enable_observability_stack ? 1 : 0
  name_prefix = "${local.name}-observability-"
  description = "Optional Grafana stack tasks: private observability traffic only"
  vpc_id      = local.platform.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  ingress {
    description = "Grafana from observability tasks"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "Prometheus from observability tasks"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "Loki from observability tasks"
    from_port   = 3100
    to_port     = 3100
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "Tempo query API from observability tasks"
    from_port   = 3200
    to_port     = 3200
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "Tempo OTLP HTTP from observability tasks"
    from_port   = 4318
    to_port     = 4318
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description     = "Tempo OTLP HTTP from app tasks"
    from_port       = 4318
    to_port         = 4318
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  ingress {
    description     = "Future FireLens delivery from app tasks to Loki"
    from_port       = 3100
    to_port         = 3100
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    description = "HTTPS to AWS APIs and object storage"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Private observability and app metrics traffic"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = [local.vpc_cidr]
  }

  tags = local.tags
}

resource "aws_security_group_rule" "app_from_observability_prometheus" {
  count                    = var.enable_observability_stack ? 1 : 0
  type                     = "ingress"
  security_group_id        = aws_security_group.app.id
  description              = "Prometheus scrape from optional observability stack"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.observability[0].id
}

################################################################################
# CloudWatch logs for observability service process logs
################################################################################

resource "aws_cloudwatch_log_group" "loki" {
  count             = var.enable_observability_stack ? 1 : 0
  name              = "/ecs/${local.name}/loki"
  kms_key_id        = aws_kms_key.cloudwatch_logs.arn
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "prometheus" {
  count             = var.enable_observability_stack ? 1 : 0
  name              = "/ecs/${local.name}/prometheus"
  kms_key_id        = aws_kms_key.cloudwatch_logs.arn
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "grafana" {
  count             = var.enable_observability_stack ? 1 : 0
  name              = "/ecs/${local.name}/grafana"
  kms_key_id        = aws_kms_key.cloudwatch_logs.arn
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "tempo" {
  count             = var.enable_observability_stack ? 1 : 0
  name              = "/ecs/${local.name}/tempo"
  kms_key_id        = aws_kms_key.cloudwatch_logs.arn
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "firelens" {
  count             = var.enable_observability_stack ? 1 : 0
  name              = "/ecs/${local.name}/firelens"
  kms_key_id        = aws_kms_key.cloudwatch_logs.arn
  retention_in_days = 14
  tags              = local.tags
}

################################################################################
# ECS task definitions and services
################################################################################

resource "aws_ecs_task_definition" "loki" {
  count                    = var.enable_observability_stack ? 1 : 0
  family                   = "${local.name}-loki"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.loki_cpu
  memory                   = var.loki_memory
  execution_role_arn       = aws_iam_role.observability_task_exec[0].arn
  task_role_arn            = aws_iam_role.loki[0].arn

  volume {
    name                = "loki-config"
    configure_at_launch = false
  }

  container_definitions = jsonencode(concat(local.firelens_router_container, [
    merge(local.ecs_container_defaults, {
      name       = "config-loader"
      image      = var.observability_config_loader_image
      essential  = false
      entryPoint = ["sh", "-c"]
      command = [
        "mkdir -p /config && aws s3 cp s3://${aws_s3_bucket.observability[0].bucket}/${aws_s3_object.loki_config[0].key} /config/loki.yml",
      ]
      mountPoints = [
        { sourceVolume = "loki-config", containerPath = "/config", readOnly = false },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.loki[0].name
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "config-loader"
        }
      }
    }),
    merge(local.ecs_container_defaults, {
      name      = "loki"
      image     = var.loki_image
      essential = true
      command   = ["-config.file=/etc/loki/loki.yml", "-log.level=warn"]
      dependsOn = [
        { containerName = "config-loader", condition = "SUCCESS" },
        { containerName = "log-router", condition = "START" },
      ]
      portMappings = [
        { containerPort = 3100, hostPort = 3100, protocol = "tcp" },
      ]
      mountPoints = [
        { sourceVolume = "loki-config", containerPath = "/etc/loki", readOnly = true },
      ]
      logConfiguration = local.firelens_log_configuration
    })
  ]))

  tags = local.tags
}

resource "aws_ecs_service" "loki" {
  count                  = var.enable_observability_stack ? 1 : 0
  name                   = "loki"
  cluster                = module.ecs.cluster_arn
  task_definition        = aws_ecs_task_definition.loki[0].arn
  desired_count          = 1
  launch_type            = "FARGATE"
  enable_execute_command = true

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    assign_public_ip = false
    security_groups  = [aws_security_group.observability[0].id]
    subnets          = local.platform.private_subnet_ids
  }

  service_registries {
    registry_arn = aws_service_discovery_service.loki[0].arn
  }

  depends_on = [
    aws_iam_role_policy.loki_s3,
    aws_iam_role_policy.loki_ssm_exec,
    aws_s3_object.loki_config,
  ]

  tags = local.tags
}

resource "aws_ecs_task_definition" "prometheus" {
  count                    = var.enable_observability_stack ? 1 : 0
  family                   = "${local.name}-prometheus"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.prometheus_cpu
  memory                   = var.prometheus_memory
  execution_role_arn       = aws_iam_role.observability_task_exec[0].arn
  task_role_arn            = aws_iam_role.prometheus[0].arn

  volume {
    name                = "prometheus-config"
    configure_at_launch = false
  }

  container_definitions = jsonencode(concat(local.firelens_router_container, [
    merge(local.ecs_container_defaults, {
      name       = "config-loader"
      image      = var.observability_config_loader_image
      essential  = false
      entryPoint = ["sh", "-c"]
      command = [
        "mkdir -p /config/rules && aws s3 cp s3://${aws_s3_bucket.observability[0].bucket}/${aws_s3_object.prometheus_config[0].key} /config/prometheus.yml && aws s3 cp s3://${aws_s3_bucket.observability[0].bucket}/${aws_s3_object.prometheus_app_alerts[0].key} /config/rules/app-alerts.yml",
      ]
      mountPoints = [
        { sourceVolume = "prometheus-config", containerPath = "/config", readOnly = false },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.prometheus[0].name
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "config-loader"
        }
      }
    }),
    merge(local.ecs_container_defaults, {
      name      = "prometheus"
      image     = var.prometheus_image
      essential = true
      command = [
        "--config.file=/etc/prometheus/prometheus.yml",
        "--storage.tsdb.path=/prometheus",
        "--log.level=warn",
      ]
      dependsOn = [
        { containerName = "config-loader", condition = "SUCCESS" },
        { containerName = "log-router", condition = "START" },
      ]
      portMappings = [
        { containerPort = 9090, hostPort = 9090, protocol = "tcp" },
      ]
      mountPoints = [
        { sourceVolume = "prometheus-config", containerPath = "/etc/prometheus", readOnly = true },
      ]
      logConfiguration = local.firelens_log_configuration
    })
  ]))

  tags = local.tags
}

resource "aws_ecs_service" "prometheus" {
  count           = var.enable_observability_stack ? 1 : 0
  name            = "prometheus"
  cluster         = module.ecs.cluster_arn
  task_definition = aws_ecs_task_definition.prometheus[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    assign_public_ip = false
    security_groups  = [aws_security_group.observability[0].id]
    subnets          = local.platform.private_subnet_ids
  }

  service_registries {
    registry_arn = aws_service_discovery_service.prometheus[0].arn
  }

  depends_on = [
    aws_ecs_service.loki,
    aws_iam_role_policy.prometheus_config_read,
    aws_s3_object.prometheus_config,
    aws_s3_object.prometheus_app_alerts,
  ]

  tags = local.tags
}

resource "aws_ecs_task_definition" "tempo" {
  count                    = var.enable_observability_stack ? 1 : 0
  family                   = "${local.name}-tempo"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.tempo_cpu
  memory                   = var.tempo_memory
  execution_role_arn       = aws_iam_role.observability_task_exec[0].arn
  task_role_arn            = aws_iam_role.tempo[0].arn

  volume {
    name                = "tempo-config"
    configure_at_launch = false
  }

  container_definitions = jsonencode(concat(local.firelens_router_container, [
    merge(local.ecs_container_defaults, {
      name       = "config-loader"
      image      = var.observability_config_loader_image
      essential  = false
      entryPoint = ["sh", "-c"]
      command = [
        "mkdir -p /config && aws s3 cp s3://${aws_s3_bucket.observability[0].bucket}/${aws_s3_object.tempo_config[0].key} /config/tempo.yml",
      ]
      mountPoints = [
        { sourceVolume = "tempo-config", containerPath = "/config", readOnly = false },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.tempo[0].name
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "config-loader"
        }
      }
    }),
    merge(local.ecs_container_defaults, {
      name      = "tempo"
      image     = var.tempo_image
      essential = true
      command   = ["-config.file=/etc/tempo/tempo.yml", "-log.level=warn"]
      dependsOn = [
        { containerName = "config-loader", condition = "SUCCESS" },
        { containerName = "log-router", condition = "START" },
      ]
      portMappings = [
        { containerPort = 3200, hostPort = 3200, protocol = "tcp" },
        { containerPort = 4317, hostPort = 4317, protocol = "tcp" },
        { containerPort = 4318, hostPort = 4318, protocol = "tcp" },
      ]
      mountPoints = [
        { sourceVolume = "tempo-config", containerPath = "/etc/tempo", readOnly = true },
      ]
      logConfiguration = local.firelens_log_configuration
    })
  ]))

  tags = local.tags
}

resource "aws_ecs_service" "tempo" {
  count           = var.enable_observability_stack ? 1 : 0
  name            = "tempo"
  cluster         = module.ecs.cluster_arn
  task_definition = aws_ecs_task_definition.tempo[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    assign_public_ip = false
    security_groups  = [aws_security_group.observability[0].id]
    subnets          = local.platform.private_subnet_ids
  }

  service_registries {
    registry_arn = aws_service_discovery_service.tempo[0].arn
  }

  depends_on = [
    aws_ecs_service.loki,
    aws_iam_role_policy.tempo_s3,
    aws_s3_object.tempo_config,
  ]

  tags = local.tags
}

resource "aws_ecs_task_definition" "grafana" {
  count                    = var.enable_observability_stack ? 1 : 0
  family                   = "${local.name}-grafana"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.grafana_cpu
  memory                   = var.grafana_memory
  execution_role_arn       = aws_iam_role.observability_task_exec[0].arn
  task_role_arn            = aws_iam_role.grafana[0].arn

  volume {
    name                = "grafana-provisioning"
    configure_at_launch = false
  }

  volume {
    name                = "grafana-dashboards"
    configure_at_launch = false
  }

  container_definitions = jsonencode(concat(local.firelens_router_container, [
    merge(local.ecs_container_defaults, {
      name       = "config-loader"
      image      = var.observability_config_loader_image
      essential  = false
      entryPoint = ["sh", "-c"]
      command = [
        "mkdir -p /provisioning/datasources /provisioning/dashboards /provisioning/alerting /provisioning/plugins /dashboards && printf 'apiVersion: 1\\n' > /provisioning/alerting/empty.yml && printf 'apiVersion: 1\\n' > /provisioning/plugins/empty.yml && aws s3 cp s3://${aws_s3_bucket.observability[0].bucket}/${aws_s3_object.grafana_datasources[0].key} /provisioning/datasources/datasources.yml && aws s3 cp s3://${aws_s3_bucket.observability[0].bucket}/${aws_s3_object.grafana_dashboards_provisioning[0].key} /provisioning/dashboards/dashboards.yml && aws s3 cp s3://${aws_s3_bucket.observability[0].bucket}/${aws_s3_object.grafana_app_dashboard[0].key} /dashboards/app-overview.json && aws s3 cp s3://${aws_s3_bucket.observability[0].bucket}/${aws_s3_object.grafana_log_groups_dashboard[0].key} /dashboards/log-groups.json",
      ]
      mountPoints = [
        { sourceVolume = "grafana-provisioning", containerPath = "/provisioning", readOnly = false },
        { sourceVolume = "grafana-dashboards", containerPath = "/dashboards", readOnly = false },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.grafana[0].name
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "config-loader"
        }
      }
    }),
    merge(local.ecs_container_defaults, {
      name      = "grafana"
      image     = var.grafana_image
      essential = true
      dependsOn = [
        { containerName = "config-loader", condition = "SUCCESS" },
        { containerName = "log-router", condition = "START" },
      ]
      secrets = [
        { name = "GF_SECURITY_ADMIN_PASSWORD", valueFrom = local.grafana_admin_secret_arn },
      ]
      environment = [
        { name = "GF_SECURITY_ADMIN_USER", value = "admin" },
        { name = "GF_USERS_ALLOW_SIGN_UP", value = "false" },
        { name = "GF_LOG_LEVEL", value = "warn" },
        { name = "GF_PLUGINS_PREINSTALL_DISABLED", value = "true" },
        { name = "PROMETHEUS_URL", value = "http://prometheus.${local.observability_dns_namespace}:9090" },
        { name = "LOKI_URL", value = "http://loki.${local.observability_dns_namespace}:3100" },
        { name = "TEMPO_URL", value = "http://tempo.${local.observability_dns_namespace}:3200" },
      ]
      portMappings = [
        { containerPort = 3000, hostPort = 3000, protocol = "tcp" },
      ]
      mountPoints = [
        { sourceVolume = "grafana-provisioning", containerPath = "/etc/grafana/provisioning", readOnly = true },
        { sourceVolume = "grafana-dashboards", containerPath = "/var/lib/grafana/dashboards", readOnly = true },
      ]
      logConfiguration = local.firelens_log_configuration
    })
  ]))

  tags = local.tags
}

resource "aws_ecs_service" "grafana" {
  count                  = var.enable_observability_stack ? 1 : 0
  name                   = "grafana"
  cluster                = module.ecs.cluster_arn
  task_definition        = aws_ecs_task_definition.grafana[0].arn
  desired_count          = 1
  launch_type            = "FARGATE"
  enable_execute_command = true

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    assign_public_ip = false
    security_groups  = [aws_security_group.observability[0].id]
    subnets          = local.platform.private_subnet_ids
  }

  service_registries {
    registry_arn = aws_service_discovery_service.grafana[0].arn
  }

  depends_on = [
    aws_ecs_service.loki,
    aws_ecs_service.prometheus,
    aws_ecs_service.tempo,
    aws_iam_role_policy.grafana_config_read,
    aws_iam_role_policy.observability_task_exec_grafana_secret,
    aws_iam_role_policy.grafana_ssm_exec,
    aws_s3_object.grafana_datasources,
    aws_s3_object.grafana_dashboards_provisioning,
    aws_s3_object.grafana_app_dashboard,
    aws_s3_object.grafana_log_groups_dashboard,
  ]

  tags = local.tags
}

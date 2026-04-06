provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

data "aws_caller_identity" "current" {}

locals {
  name       = "db-migration-example-${var.environment}"
  account_id = data.aws_caller_identity.current.account_id
  # Use var.aws_region directly — data.aws_region.current.name is deprecated in aws provider v6
  region = var.aws_region
  azs    = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  tags = {
    Project     = "db-migration-example"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

################################################################################
# Networking — terraform-aws-modules/vpc/aws ~> 6.0
# Three tiers: public (ALB), private (ECS), intra (RDS — no internet route).
# single_nat_gateway=true saves ~$32/mo in non-prod. Set false for prod HA.
################################################################################

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0"

  name = local.name
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, 100 + i)]
  intra_subnets   = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, 200 + i)]

  enable_nat_gateway     = true
  single_nat_gateway     = var.single_nat_gateway
  one_nat_gateway_per_az = !var.single_nat_gateway

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = local.tags
}

################################################################################
# ECR — terraform-aws-modules/ecr/aws ~> 3.0
# IMMUTABLE tags prevent silent overwrites of a deployed SHA in prod.
# scan_on_push enables free basic CVE scanning on every push.
# Lifecycle: expire untagged after 1 day, keep last 10 sha- tagged images.
################################################################################

module "ecr_app" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 3.0"

  repository_name                 = "${local.name}/app"
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
# ECR — liquibase migrations image
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
# RDS — terraform-aws-modules/rds/aws ~> 7.0
# manage_master_user_password=true: RDS generates and rotates the password in
# Secrets Manager automatically. v7 drops `password` in favour of write-only
# `password_wo` — with manage_master_user_password=true neither is needed.
# deletion_protection and skip_final_snapshot are tied to rds_multi_az (prod).
################################################################################

resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "Postgres from ECS app tasks only - no public access"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "Postgres from ECS app tasks"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    # aws_security_group.app is pre-created so both RDS and ECS module can
    # reference it without a circular dependency. The ECS module is told to
    # use it via security_group_ids + create_security_group=false.
    security_groups = [aws_security_group.app.id]
  }

  tags = local.tags
}

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 7.0"

  identifier = local.name

  engine               = "postgres"
  engine_version       = "16"
  family               = "postgres16"
  major_engine_version = "16"
  instance_class       = var.rds_instance_class

  allocated_storage     = var.rds_allocated_storage_gb
  max_allocated_storage = var.rds_allocated_storage_gb * 5
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "migration_example"
  username = "app"
  port     = "5432"

  # RDS manages the password in Secrets Manager and rotates it automatically
  manage_master_user_password = true

  multi_az               = var.rds_multi_az
  create_db_subnet_group = true
  subnet_ids             = module.vpc.intra_subnets
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  performance_insights_enabled          = true
  performance_insights_retention_period = 7 # free tier; 731 days is paid

  deletion_protection        = var.rds_multi_az # true in prod, false in dev
  skip_final_snapshot        = !var.rds_multi_az
  auto_minor_version_upgrade = true
  apply_immediately          = false

  tags = local.tags
}

################################################################################
# ALB — native resources (single listener + target group)
################################################################################

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "ALB: HTTP from internet, egress to app tasks"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "HTTP from allowed CIDR"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.alb_ingress_cidr]
  }

  egress {
    description = "All egress to app tasks"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "App tasks: inbound from ALB only, all egress"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "From ALB on container port"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "All egress for ECR, Secrets Manager, CloudWatch"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_lb" "this" {
  name               = local.name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
  # Drop invalid HTTP headers — prevents header smuggling attacks at no cost.
  drop_invalid_header_fields = true
  tags                       = local.tags
}

resource "aws_lb_target_group" "app" {
  name        = local.name
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip" # required for Fargate — each task gets its own ENI

  deregistration_delay = 10

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    # 10s interval: 2 consecutive successes = ~20s after task is healthy.
    # Default is 30s (60s to mark healthy) — this alone saves ~40s per deploy.
    interval = 10
    timeout  = 5
    matcher  = "200"
  }

  tags = local.tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

################################################################################
# ECS task execution role — created explicitly so worker and liquibase task
# definitions can reference it without depending on module.ecs outputs, which
# are null during the same plan that creates those resources.
################################################################################

data "aws_iam_policy_document" "task_exec_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_exec" {
  name               = "${local.name}-task-exec"
  assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "task_exec_managed" {
  role       = aws_iam_role.task_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_exec_secrets" {
  name = "rds-secret-access"
  role = aws_iam_role.task_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = module.rds.db_instance_master_user_secret_arn
    }]
  })
}

################################################################################
# ECS — terraform-aws-modules/ecs/aws ~> 7.0
# v7: cluster_capacity_providers must be explicit — no longer inferred.
# task_exec_secret_arns is top-level — wires the shared execution role to the
# RDS secret so ECS injects DATABASE_URL at startup without AWS SDK calls.
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
      # 30s covers Fargate cold start + secret fetch + app startup for this service.
      health_check_grace_period_seconds = 30

      # Use the explicitly managed execution role so our secret policy applies.
      # Without this the module creates its own role that lacks GetSecretValue.
      create_task_exec_iam_role = false
      task_exec_iam_role_arn    = aws_iam_role.task_exec.arn
      # Enables `aws ecs execute-command` for interactive access to running tasks.
      # Required for DB access via SSM port forwarding — no bastion needed.
      enable_execute_command = true
      # Explicit family name — module default uses the service key ("app") which
      # is shared across environments. Scoping to local.name isolates dev and prod.
      family = local.name

      container_definitions = {
        # PgBouncer sidecar — runs in the same task network namespace as the app.
        # The app's DATABASE_URL points to localhost:5432 (pgbouncer), not RDS directly.
        # transaction mode: server connections are returned to the pool after each
        # transaction, multiplexing many app connections onto a small RDS pool.
        # pgbouncer connects to RDS using the secret injected via DB_HOST / DB_PORT /
        # DB_NAME / DB_USER / DB_PASSWORD environment variables.
        pgbouncer = {
          # Mirrored to ECR by CI to avoid Docker Hub unauthenticated pull rate limits.
          # Upstream: edoburu/pgbouncer:v1.25.1-p0
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
            { name = "DB_NAME", value = "migration_example" },
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
          # Explicit name — module default (/aws/ecs/app/pgbouncer) is shared across
          # environments because it derives from the service key, not the cluster name.
          cloudwatch_log_group_name = "/ecs/${local.name}/pgbouncer"
        }

        app = {
          # Placeholder — app.yml patches this to the real SHA tag at release time
          # via amazon-ecs-render-task-definition. Infra owns the task definition shape,
          # not the image tag.
          image     = "${module.ecr_app.repository_url}:placeholder"
          essential = true

          # ECS container definition keys are camelCase — they map directly to the ECS API
          portMappings = [{ containerPort = 8000, protocol = "tcp" }]

          # ECS does not interpolate $(VAR) in environment values. DB_PASSWORD is
          # injected as a secret; the app's config.py composes DATABASE_URL at startup.
          secrets = [
            { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
          ]

          environment = []

          # pgbouncer must be accepting connections before the app starts.
          dependsOn = [{ containerName = "pgbouncer", condition = "START" }]

          healthCheck = {
            command = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\""]
            # Tight intervals — app starts in <2s. startPeriod covers Fargate cold start
            # (~30s). After that, 5s interval means ECS marks healthy within 10s of ready.
            interval    = 5
            timeout     = 3
            retries     = 3
            startPeriod = 30
          }

          # readonlyRootFilesystem = false: ECS Exec (SSM agent) requires write access to
          # /var/lib/amazon and /var/log/amazon at startup — it does not support readonly
          # root even with tmpfs mounts on Fargate 1.4. The module defaults to true, so
          # we explicitly opt out. The meaningful security boundary here is IAM + network
          # (private subnet, security groups), not filesystem immutability.
          readonlyRootFilesystem = false

          enable_cloudwatch_logging              = true
          cloudwatch_log_group_retention_in_days = 30
          # Explicit name — module default (/aws/ecs/app/app) is shared across
          # environments because it derives from the service key, not the cluster name.
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

      subnet_ids = module.vpc.private_subnets
      vpc_id     = module.vpc.vpc_id

      # Use the pre-created SG so RDS can reference it without a circular
      # dependency (RDS SG → app SG → ECS module → RDS endpoint → RDS → RDS SG).
      create_security_group = false
      security_group_ids    = [aws_security_group.app.id]
    }
  }

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
      # Placeholder — release pipeline patches this at deploy time.
      image     = "${module.ecr_worker.repository_url}:placeholder"
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
# ECS Exec — SSM permissions on the app task role
# Required for `aws ecs execute-command` and SSM port forwarding to RDS.
# No bastion host needed — SSM tunnels through the running Fargate task.
################################################################################

resource "aws_iam_role_policy" "task_ssm_exec" {
  name = "ssm-exec"
  role = module.ecs.services["app"].tasks_iam_role_name

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
      # Placeholder — release pipeline patches this at deploy time.
      image     = "${module.ecr_liquibase.repository_url}:placeholder"
      essential = true

      secrets = [
        # RDS-managed secret only has username + password. Host/port/dbname are static.
        # Injected directly as the Liquibase env vars — ECS $(VAR) interpolation only
        # works in command/entryPoint, not in environment values.
        { name = "LIQUIBASE_COMMAND_USERNAME", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:username::" },
        { name = "LIQUIBASE_COMMAND_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
      ]

      environment = [
        { name = "LIQUIBASE_COMMAND_URL", value = "jdbc:postgresql://${module.rds.db_instance_address}:${module.rds.db_instance_port}/migration_example" },
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

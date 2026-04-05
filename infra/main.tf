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
    description     = "Postgres from app security group"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
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

  deregistration_delay = 30

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
    matcher             = "200"
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

      container_definitions = {
        # PgBouncer sidecar — runs in the same task network namespace as the app.
        # The app's DATABASE_URL points to localhost:5432 (pgbouncer), not RDS directly.
        # transaction mode: server connections are returned to the pool after each
        # transaction, multiplexing many app connections onto a small RDS pool.
        # pgbouncer connects to RDS using the secret injected via DB_HOST / DB_PORT /
        # DB_NAME / DB_USER / DB_PASSWORD environment variables.
        pgbouncer = {
          # edoburu/pgbouncer:v1.25.1-p0 — versioned tag, multi-arch (amd64 + arm64).
          # Pin to digest in prod: edoburu/pgbouncer@sha256:cf8ba55692e4818e983dc047acf1711f17dd4ab1da7d47bdab8b9b2cc14337dc
          image     = "edoburu/pgbouncer:v1.25.1-p0"
          essential = true

          secrets = [
            { name = "DB_HOST", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:host::" },
            { name = "DB_PORT", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:port::" },
            { name = "DB_NAME", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:dbname::" },
            { name = "DB_USER", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:username::" },
            { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
          ]

          # edoburu/pgbouncer reads DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
          # directly from the injected secrets above — no need to re-declare them
          # as environment variables. Only pool config goes here.
          environment = [
            { name = "POOL_MODE", value = "transaction" },
            { name = "DEFAULT_POOL_SIZE", value = tostring(var.pgbouncer_pool_size) },
            { name = "MAX_CLIENT_CONN", value = "200" },
            { name = "AUTH_TYPE", value = "scram-sha-256" },
          ]

          enable_cloudwatch_logging              = true
          cloudwatch_log_group_retention_in_days = 14
        }

        app = {
          # Placeholder — deploy.yml patches this to the real SHA tag at release time
          # via amazon-ecs-render-task-definition. Infra owns the task definition shape,
          # not the image tag.
          image     = "${module.ecr_app.repository_url}:placeholder"
          essential = true

          # ECS container definition keys are camelCase — they map directly to the ECS API
          portMappings = [{ containerPort = 8000, protocol = "tcp" }]

          # The app container needs DB_USER and DB_PASSWORD to construct DATABASE_URL.
          # Injected as separate secrets so ECS resolves them at task start.
          # DATABASE_URL is then composed as a plain env var — no $(VAR) interpolation
          # needed since the URL is built from the known static username "app" and
          # the password secret field injected directly.
          secrets = [
            { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
          ]

          environment = [
            # Username is static ("app" — set in module.rds). Password comes from
            # the secret injected above. $(DB_PASSWORD) interpolation works here
            # because DB_PASSWORD is declared in the secrets block of this container.
            { name = "DATABASE_URL", value = "postgresql://app:$(DB_PASSWORD)@localhost:5432/migration_example" },
          ]

          # pgbouncer must be accepting connections before the app starts.
          dependsOn = [{ containerName = "pgbouncer", condition = "START" }]

          healthCheck = {
            command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\""]
            interval    = 15
            timeout     = 5
            retries     = 3
            startPeriod = 15
          }

          enable_cloudwatch_logging              = true
          cloudwatch_log_group_retention_in_days = 30
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

      security_group_ingress_rules = {
        from_alb = {
          description                  = "From ALB on container port"
          from_port                    = "8000"
          to_port                      = "8000"
          ip_protocol                  = "tcp"
          referenced_security_group_id = aws_security_group.alb.id
        }
      }
      security_group_egress_rules = {
        all = { ip_protocol = "-1", cidr_ipv4 = "0.0.0.0/0" }
      }
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
        # Inject individual fields from the RDS secret and compose the URL.
        # Worker bypasses pgbouncer — uses the raw RDS endpoint directly.
        { name = "DB_HOST", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:host::" },
        { name = "DB_PORT", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:port::" },
        { name = "DB_NAME", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:dbname::" },
        { name = "DB_USER", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
      ]
      environment = [
        { name = "BACKFILL_DATABASE_URL", value = "postgresql://$(DB_USER):$(DB_PASSWORD)@$(DB_HOST):$(DB_PORT)/$(DB_NAME)" },
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
# Uses a custom image built FROM liquibase/liquibase:4.27 with the db/changelog/
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
        { name = "DB_HOST", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:host::" },
        { name = "DB_PORT", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:port::" },
        { name = "DB_NAME", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:dbname::" },
        { name = "DB_USER", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${module.rds.db_instance_master_user_secret_arn}:password::" },
      ]

      environment = [
        { name = "LIQUIBASE_COMMAND_URL", value = "jdbc:postgresql://$(DB_HOST):$(DB_PORT)/$(DB_NAME)" },
        { name = "LIQUIBASE_COMMAND_USERNAME", value = "$(DB_USER)" },
        { name = "LIQUIBASE_COMMAND_PASSWORD", value = "$(DB_PASSWORD)" },
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

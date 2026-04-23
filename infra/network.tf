################################################################################
# Networking — terraform-aws-modules/vpc/aws ~> 6.0
# Three tiers: public (ALB), private (ECS), intra (RDS — no internet route).
# The stack stays intentionally lean: one NAT gateway and a single-AZ database.
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
# RDS — terraform-aws-modules/rds/aws ~> 7.0
# manage_master_user_password=true: RDS generates and rotates the password in
# Secrets Manager automatically. v7 drops `password` in favour of write-only
# `password_wo` — with manage_master_user_password=true neither is needed.
# deletion_protection and skip_final_snapshot are tied to rds_multi_az.
################################################################################

resource "aws_security_group" "rds" {
  # name_prefix + create_before_destroy: same reason as alb SG — description
  # changes force replacement and a fixed name collides in the same VPC.
  name_prefix = "${local.name}-rds-"
  description = "Postgres from ECS app tasks only - no public access"
  vpc_id      = module.vpc.vpc_id

  lifecycle {
    create_before_destroy = true
  }

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

  db_name  = "aws_sdlc_containers"
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

  deletion_protection        = var.rds_multi_az # stays off in the lean single-AZ default
  skip_final_snapshot        = !var.rds_multi_az
  auto_minor_version_upgrade = true
  apply_immediately          = false

  tags = local.tags
}

################################################################################
# VPC Interface Endpoints — ECR, Secrets Manager, CloudWatch Logs
# Allows ECS tasks to reach AWS APIs without traversing the NAT Gateway.
# With these endpoints the app SG egress can be restricted to the VPC CIDR,
# satisfying CKV_AWS_25 / CKV_AWS_277 / CKV_AWS_382.
# Cost: ~$7.30/mo per endpoint per AZ (Interface endpoints are billed hourly).
# 4 endpoints × 2 AZs = ~$58/mo — offset by reduced NAT data-processing charges
# at any meaningful request volume.
################################################################################

resource "aws_security_group" "vpc_endpoints" {
  # name_prefix + create_before_destroy: same reason as alb SG — description
  # changes force replacement and a fixed name collides in the same VPC.
  name_prefix = "${local.name}-vpc-endpoints-"
  description = "Allow HTTPS from private subnets to AWS Interface Endpoints"
  vpc_id      = module.vpc.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  ingress {
    description = "HTTPS from ECS tasks"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = local.tags
}

# ECR API — image manifest and auth calls
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-ecr-api" })
}

# ECR DKR — image layer pulls
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-ecr-dkr" })
}

# Secrets Manager — DB password injection at task startup
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-secretsmanager" })
}

# CloudWatch Logs — container log delivery from awslogs driver
resource "aws_vpc_endpoint" "logs" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-logs" })
}

# S3 Gateway Endpoint — ECR stores image layers in S3; Gateway endpoints are free
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${local.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids
  tags              = merge(local.tags, { Name = "${local.name}-s3" })
}

# SSM Messages — required for ECS Exec (db-tunnel, db-exec) and SSM Session Manager.
# Without this, tasks in private subnets cannot establish SSM sessions (TargetNotConnected).
resource "aws_vpc_endpoint" "ssmmessages" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.ssmmessages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-ssmmessages" })
}

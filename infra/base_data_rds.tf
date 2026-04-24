################################################################################
# Base data — RDS
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

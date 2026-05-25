################################################################################
# Application database
#
# RDS is the AWS implementation here, but the file boundary is the app's
# primary relational persistence.
#
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
  vpc_id      = local.platform.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  ingress {
    description = "Postgres from ECS app tasks"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    # aws_security_group.primary_edge is pre-created so both RDS and ECS module can
    # reference it without a circular dependency. The ECS module is told to
    # use it via security_group_ids + create_security_group=false.
    security_groups = [aws_security_group.primary_edge.id]
  }

  tags = local.tags
}

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 7.0"

  identifier = local.name

  engine               = "postgres"
  engine_version       = "18.3"
  family               = "postgres18"
  major_engine_version = "18"
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
  subnet_ids             = local.platform.intra_subnet_ids
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

resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${local.name}-rds-cpu-high"
  alarm_description   = "RDS CPU utilization exceeded 80 percent. Runbook: docs/runbooks/rds-pressure.md"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  threshold           = 80
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  treat_missing_data  = "notBreaching"
  unit                = "Percent"

  dimensions = {
    DBInstanceIdentifier = module.rds.db_instance_identifier
  }

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage_low" {
  alarm_name          = "${local.name}-rds-free-storage-low"
  alarm_description   = "RDS free storage fell below 20 percent of initially allocated storage. Runbook: docs/runbooks/rds-pressure.md"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  threshold           = var.rds_allocated_storage_gb * 1024 * 1024 * 1024 * 0.2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  treat_missing_data  = "notBreaching"
  unit                = "Bytes"

  dimensions = {
    DBInstanceIdentifier = module.rds.db_instance_identifier
  }

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_connections_high" {
  alarm_name          = "${local.name}-rds-connections-high"
  alarm_description   = "RDS database connections exceeded the lean stack pressure threshold. Runbook: docs/runbooks/rds-pressure.md"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  threshold           = 70
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  treat_missing_data  = "notBreaching"
  unit                = "Count"

  dimensions = {
    DBInstanceIdentifier = module.rds.db_instance_identifier
  }

  tags = local.tags
}

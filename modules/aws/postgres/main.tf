################################################################################
# PostgreSQL
#
# One RDS instance in subnets with no egress route, reachable only from the
# security groups that name it. The master credential is managed by RDS and
# rotated by RDS, so no password ever passes through Terraform state or CI.
#
# Clients attach the exported client security group rather than opening a CIDR.
################################################################################

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids

  tags = var.tags
}

resource "aws_security_group" "client" {
  name_prefix = "${var.name}-client-"
  description = "Attach to a workload that may reach the ${var.name} database"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_security_group" "database" {
  name_prefix = "${var.name}-db-"
  description = "Database ingress for ${var.name}"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "from_clients" {
  security_group_id            = aws_security_group.database.id
  description                  = "PostgreSQL from workloads holding the client group"
  referenced_security_group_id = aws_security_group.client.id
  from_port                    = var.port
  to_port                      = var.port
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "client_to_database" {
  security_group_id            = aws_security_group.client.id
  description                  = "Client to PostgreSQL"
  referenced_security_group_id = aws_security_group.database.id
  from_port                    = var.port
  to_port                      = var.port
  ip_protocol                  = "tcp"
}

resource "aws_kms_key" "this" {
  count = var.kms_key_arn == null ? 1 : 0

  description             = "Storage encryption for the ${var.name} database"
  enable_key_rotation     = true
  deletion_window_in_days = 30

  tags = var.tags
}

resource "aws_kms_alias" "this" {
  count = var.kms_key_arn == null ? 1 : 0

  name          = "alias/${var.name}-postgres"
  target_key_id = aws_kms_key.this[0].key_id
}

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name}-"
  family      = var.parameter_group_family
  description = "Parameters for ${var.name}"

  dynamic "parameter" {
    for_each = var.parameters
    content {
      name         = parameter.key
      value        = parameter.value
      apply_method = "pending-reboot"
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_db_instance" "this" {
  # checkov:skip=CKV_AWS_157:multi_az is a caller availability/cost choice; enable it for production.
  # checkov:skip=CKV_AWS_118:Enhanced monitoring requires a consumer monitoring role; standard RDS metrics and PostgreSQL logs are enabled.

  identifier     = var.name
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.database_name
  username = var.master_username
  port     = var.port

  manage_master_user_password = true
  # Use the Secrets Manager service key so ECS can fetch credentials without a separate KMS grant.
  iam_database_authentication_enabled = true

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_arn == null ? aws_kms_key.this[0].arn : var.kms_key_arn

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.database.id]
  parameter_group_name   = aws_db_parameter_group.this.name
  multi_az               = var.multi_az
  publicly_accessible    = false

  backup_retention_period   = var.backup_retention_days
  backup_window             = var.backup_window
  maintenance_window        = var.maintenance_window
  copy_tags_to_snapshot     = true
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name}-final"

  auto_minor_version_upgrade      = true
  apply_immediately               = var.apply_immediately
  performance_insights_enabled    = var.performance_insights_enabled
  performance_insights_kms_key_id = var.kms_key_arn == null ? aws_kms_key.this[0].arn : var.kms_key_arn
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = var.tags

  lifecycle {
    precondition {
      condition     = var.deletion_protection || !var.skip_final_snapshot
      error_message = "A database with neither deletion protection nor a final snapshot can be destroyed with no recovery path. Enable one."
    }
  }
}

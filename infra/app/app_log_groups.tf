################################################################################
# Api log groups
#
# These log groups are root-owned so api task-definition ownership can leave the
# ECS service module after bootstrap without dropping log retention/KMS ownership.
################################################################################

resource "aws_cloudwatch_log_group" "api" {
  name              = local.workload_log_group_names["api"]
  retention_in_days = 30
  kms_key_id        = aws_kms_key.cloudwatch_logs.arn

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "pgbouncer" {
  name              = "/ecs/${local.name}/pgbouncer"
  retention_in_days = 14
  kms_key_id        = aws_kms_key.cloudwatch_logs.arn

  tags = local.tags
}

################################################################################
# App log groups
#
# These log groups are root-owned so app task-definition ownership can leave the
# ECS service module after bootstrap without dropping log retention/KMS ownership.
################################################################################

moved {
  from = module.ecs.module.service["app"].module.container_definition["app"].aws_cloudwatch_log_group.this[0]
  to   = aws_cloudwatch_log_group.app
}

moved {
  from = module.ecs.module.service["app"].module.container_definition["pgbouncer"].aws_cloudwatch_log_group.this[0]
  to   = aws_cloudwatch_log_group.pgbouncer
}

resource "aws_cloudwatch_log_group" "app" {
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

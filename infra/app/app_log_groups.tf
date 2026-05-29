################################################################################
# Primary edge log groups
#
# These log groups are root-owned so primary edge task-definition ownership can
# leave the ECS service module after bootstrap without dropping
# log retention/KMS ownership.
################################################################################

resource "aws_cloudwatch_log_group" "primary_edge" {
  name              = local.workload_log_group_names[local.primary_edge_workload_name]
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

resource "aws_cloudwatch_log_group" "adot" {
  name              = "/ecs/${local.name}/adot"
  retention_in_days = 14
  kms_key_id        = aws_kms_key.cloudwatch_logs.arn

  tags = local.tags
}

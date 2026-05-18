# Data Export Job Failure

Use this runbook when the
`aws-sdlc-containers-data-export-scheduler-target-errors` or
`aws-sdlc-containers-data-export-success-missing` CloudWatch alarm is in
`ALARM`.

## What The Alarm Means

The alarm watches `AWS/Scheduler` `TargetErrorCount` for the default schedule
group. It fires when EventBridge Scheduler cannot deliver the ECS `RunTask`
target for the data export job.

This is a scheduler-to-ECS delivery signal. If the task starts and the
container exits non-zero, inspect the ECS task and CloudWatch logs even if this
alarm does not fire.

The success-missing alarm watches the custom `aws-sdlc-containers/DataExport`
`SuccessCount` metric emitted from successful manifest log lines. It fires when
no successful export is observed for two consecutive daily evaluation windows.

## First Checks

If `terraform -chdir=infra/app output -raw data_export_success_cloudwatch_alarm_enabled`
returns `false`, the success-missing CloudWatch alarm was intentionally
disabled. Still check the Scheduler delivery alarm, then use the Grafana
freshness checks below.

Confirm the alarm and schedule:

```bash
aws cloudwatch describe-alarms \
  --alarm-names \
    "$(terraform -chdir=infra/app output -raw data_export_scheduler_target_errors_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw data_export_success_missing_alarm_name)" \
  --region eu-central-1

aws scheduler get-schedule \
  --group-name default \
  --name "$(terraform -chdir=infra/app output -raw data_export_schedule_name)" \
  --region eu-central-1
```

Check recent stopped tasks for the data export family:

```bash
aws ecs list-tasks \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --family aws-sdlc-containers-data-export-job \
  --desired-status STOPPED \
  --region eu-central-1
```

Describe any recent task ARN returned by `list-tasks`:

```bash
aws ecs describe-tasks \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --tasks "<task-arn>" \
  --region eu-central-1
```

Inspect application logs:

```bash
aws logs tail /ecs/aws-sdlc-containers/data-export-job \
  --since 2h \
  --region eu-central-1
```

## Grafana Checks

When a reachable Loki endpoint contains data export logs, inspect successful
and failed manifest log records there before changing CloudWatch alarms:

```logql
{stack="aws-sdlc-containers", service="data-export-job"} | json | dataset="order_contact_email"
```

A future Grafana freshness alert should be based on either that successful
manifest log record or a native data-export job metric. Until that replacement
is deployed, the CloudWatch `SuccessCount` metric filter and success-missing
alarm remain authoritative.

## Common Causes

- Scheduler role cannot call `ecs:RunTask` or pass the task roles.
- Data export task definition has no active revision.
- Private subnet or security group selection prevents task startup.
- ECS capacity or account limits reject the task.
- Container starts but fails because database or S3 access is misconfigured.

## Recovery

After fixing the underlying issue, run the current task definition once from a
private subnet:

```bash
GITHUB_OUTPUT=/tmp/data-export-network.env \
  scripts/ci/ci_resolve_ecs_network.sh aws-sdlc-containers
source /tmp/data-export-network.env

export ECS_RUN_TASK_WAIT_FOR_STOPPED=true
export ECS_RUN_TASK_ASSERT_SUCCESS=true
export ECS_RUN_TASK_LABEL="Data export job"

TASK_ARN=$(scripts/ci/ci_run_ecs_task.sh \
  "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  "aws-sdlc-containers-data-export-job" \
  "$subnet_id" \
  "$sg_id")
```

Confirm that the expected S3 objects exist:

```bash
aws s3 ls \
  "s3://$(terraform -chdir=infra/app output -raw data_hub_bucket_name)/raw/order_contact_email/" \
  --recursive \
  --region eu-central-1

aws s3 ls \
  "s3://$(terraform -chdir=infra/app output -raw data_hub_bucket_name)/manifests/order_contact_email/" \
  --recursive \
  --region eu-central-1
```

The alarm returns to `OK` after the next evaluation window has no target
delivery errors or after the success metric has enough clean daily evaluation
windows.

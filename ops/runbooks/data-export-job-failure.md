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
returns `false`, the success-missing CloudWatch alarm was intentionally disabled
after Grafana-stack dual-run. Still check the Scheduler delivery alarm, then use
the Grafana-stack freshness checks below.

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

## Grafana-Stack Checks

When the optional Grafana stack is enabled and data export job logs are routed
to Loki, inspect successful and failed manifest log records there before
changing CloudWatch alarms:

```logql
{container="data-export-job"} | json | dataset="order_contact_email"
```

A future Grafana-stack freshness alert should be based on either that successful
manifest log record or a native data-export job metric. Until that replacement
is deployed and dual-run, the CloudWatch `SuccessCount` metric filter and
success-missing alarm remain authoritative.

## Common Causes

- Scheduler role cannot call `ecs:RunTask` or pass the task roles.
- Data export task definition has no active revision.
- Private subnet or security group selection prevents task startup.
- ECS capacity or account limits reject the task.
- Container starts but fails because database or S3 access is misconfigured.

## Recovery

After fixing the underlying issue, run the current task definition once from a
private subnet using the existing helper scripts:

```bash
GITHUB_OUTPUT=/tmp/data-export-network.env \
  scripts/ci_resolve_ecs_network.sh aws-sdlc-containers
source /tmp/data-export-network.env

TASK_ARN=$(scripts/ci_run_ecs_task.sh \
  "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  "aws-sdlc-containers-data-export-job" \
  "$subnet_id" \
  "$sg_id")

aws ecs wait tasks-stopped \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --tasks "$TASK_ARN" \
  --region eu-central-1

scripts/ci_assert_ecs_task_succeeded.sh \
  "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  "$TASK_ARN" \
  "Data export job"
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

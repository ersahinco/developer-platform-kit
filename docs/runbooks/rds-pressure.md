# RDS Pressure

Use this runbook when any of these CloudWatch alarms are in `ALARM`:

- `rds-cpu-high`
- `rds-free-storage-low`
- `rds-connections-high`

Use Terraform outputs and environment variables in examples:

```bash
export AWS_REGION="${AWS_REGION:-eu-central-1}"
export STACK_NAME="${STACK_NAME:-<stack-name>}"
```

## What The Alarms Mean

The alarms watch the RDS instance metrics in the `AWS/RDS` namespace:

- `CPUUtilization` above 80 percent.
- `FreeStorageSpace` below 20 percent of the initially allocated storage.
- `DatabaseConnections` above 70 connections.

The connection threshold is intentionally below the approximate connection
ceiling for the lean `db.t4g.small` default so operators see pressure before
the database is exhausted.

## First Checks

Confirm alarm state:

```bash
aws cloudwatch describe-alarms \
  --alarm-names \
    "$(terraform -chdir=infra/app output -raw rds_cpu_high_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw rds_free_storage_low_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw rds_connections_high_alarm_name)" \
  --region "$AWS_REGION"
```

Inspect the DB instance:

```bash
aws rds describe-db-instances \
  --db-instance-identifier "$(terraform -chdir=infra/app output -raw rds_instance_identifier)" \
  --region "$AWS_REGION"
```

Check app and PgBouncer logs for connection or timeout symptoms:

```bash
PRIMARY_EDGE_SERVICE="$(terraform -chdir=infra/app output -raw primary_edge_service_name)"

aws logs tail "/ecs/${STACK_NAME}/${PRIMARY_EDGE_SERVICE}" \
  --since 30m \
  --region "$AWS_REGION"

aws logs tail "/ecs/${STACK_NAME}/pgbouncer" \
  --since 30m \
  --region "$AWS_REGION"
```

## Common Causes

- Backfill or data export is running at the same time as app traffic.
- Slow or blocked database queries increase CPU and connection hold time.
- PgBouncer pool pressure causes requests to wait.
- Test or operator sessions are holding direct database connections.
- Storage growth from tables, indexes, WAL, or failed cleanup is faster than expected.

## Recovery

For CPU or connection pressure:

1. Pause non-critical one-off tasks such as backfill or manual data exports.
2. Check app logs for slow request patterns or repeated failures.
3. Reduce traffic or roll back the last app revision if pressure began after a deploy.
4. Increase `pgbouncer_pool_size`, app task sizing, or RDS instance class only after logs and metrics identify the bottleneck.

For low storage:

1. Confirm whether RDS storage autoscaling is increasing allocated storage.
2. Avoid destructive cleanup until table/index growth is understood.
3. If free space keeps falling, increase `rds_allocated_storage_gb` and apply Terraform.

Confirm recovery:

```bash
aws cloudwatch describe-alarms \
  --alarm-names \
    "$(terraform -chdir=infra/app output -raw rds_cpu_high_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw rds_free_storage_low_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw rds_connections_high_alarm_name)" \
  --region "$AWS_REGION"

curl -fsS "https://$(terraform -chdir=infra/app output -raw primary_edge_fqdn)/health"
```

The alarms return to `OK` after the next clean evaluation windows.

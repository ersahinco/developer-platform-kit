# ECS Deploy Rollback

Use this runbook when an app deploy causes unhealthy targets, target 5xxs,
latency alarms, or another operator-confirmed regression.

This rollback changes only the running ECS service task definition. It does not
undo database migrations, runtime `WRITE_MODE` or `READ_MODE` values, or one-off
worker/data-export task definitions.

For a no-data practice path, use the GitHub Actions workflow
`App No-Data Rollback Drill`. It deploys only an app service revision with
disabled-by-default fault-injection environment variables set to make `/ready`
slow or erroring. ECS deployment circuit breaker and deployment CloudWatch
alarms perform the rollback automatically to the last completed app service
revision. The workflow does not run Liquibase, backfill, data export, or runtime
mode changes.

Run the drill twice when practicing:

- `fault_mode=error` makes `/ready` return 503 and should trip the ALB target
  5xx deployment alarm.
- `fault_mode=latency` delays `/ready` and should trip the ALB p95 latency
  deployment alarm.

## Before Rolling Back

Confirm the current service state:

```bash
aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw app_service_name)" \
  --region eu-central-1 \
  --query 'services[0].{status:status,taskDefinition:taskDefinition,deployments:deployments[*].{status:status,taskDefinition:taskDefinition,rolloutState:rolloutState,running:runningCount,pending:pendingCount}}'
```

List recent active app task definition revisions:

```bash
aws ecs list-task-definitions \
  --family-prefix aws-sdlc-containers \
  --status ACTIVE \
  --sort DESC \
  --max-items 10 \
  --region eu-central-1
```

Choose the most recent known-good revision from the list. Prefer the revision
that was healthy immediately before the bad deploy. If the deploy also advanced
schema phase or runtime flags, confirm the target revision is compatible with
the current database state before updating the service.

## Roll Back The Service

Set the target revision explicitly:

```bash
PREVIOUS_TASK_DEFINITION_ARN="<previous-task-definition-arn>"
```

Update the service:

```bash
aws ecs update-service \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --service "$(terraform -chdir=infra/app output -raw app_service_name)" \
  --task-definition "$PREVIOUS_TASK_DEFINITION_ARN" \
  --force-new-deployment \
  --region eu-central-1
```

Wait for stabilization:

```bash
aws ecs wait services-stable \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw app_service_name)" \
  --region eu-central-1
```

## Verify Recovery

Check the public health endpoint:

```bash
curl -fsS "https://$(terraform -chdir=infra/app output -raw api_fqdn)/health"
```

Confirm alarms and service events:

```bash
aws cloudwatch describe-alarms \
  --alarm-names \
    "$(terraform -chdir=infra/app output -raw app_unhealthy_targets_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw app_target_5xx_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw app_target_latency_alarm_name)" \
  --region eu-central-1

aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw app_service_name)" \
  --region eu-central-1 \
  --query 'services[0].events[:10]'
```

The alarms return to `OK` after their next clean evaluation windows.

## After Recovery

Record the bad and restored task definition ARNs in the incident notes. Keep the
bad revision active until the failure is understood unless it contains a known
secret or security exposure.

If runtime flags were changed during the failed deploy, use `docs/deployment.md`
to return `WRITE_MODE` or `READ_MODE` to the last compatible value.

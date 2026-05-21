# ECS Deploy Rollback

Use this runbook when an ECS service deploy causes unhealthy targets, target
5xxs, latency alarms, failure to stabilize, or another operator-confirmed
regression.

This rollback changes only the running ECS service task definition. It does not
undo database migrations, runtime `WRITE_MODE` or `READ_MODE` values, or one-off
worker/data-export task definitions.

The app and event consumer ECS services use the ECS native deployment
circuit breaker with rollback enabled. The app service also uses ECS deployment
CloudWatch alarms for ALB target 5xx and latency symptoms. The app
rolling deployment keeps a five-minute bake window so delayed CloudWatch latency
datapoints can still trigger ECS automatic rollback before the revision is
accepted as completed. One-off tasks such as Liquibase, backfill, and data
export do not have ECS service rollback; their recovery path is rerun, stop, or
restore according to their specific runbook.

For a no-data practice path, use the GitHub Actions workflow
`App No-Data Rollback Drill`. It deploys only an app service revision with
disabled-by-default fault-injection environment variables set to make `/ready`
slow or erroring. ECS deployment circuit breaker and deployment CloudWatch
alarms perform the rollback automatically to the last completed app service
revision. The workflow does not run Liquibase, backfill, data export, or runtime
mode changes. The latency path can take over ten minutes because ECS waits
through the deployment bake window and then stabilizes the restored revision.

Run the drill twice when practicing:

- `fault_mode=error` makes `/ready` return 503 and should trip the ALB target
  5xx deployment alarm.
- `fault_mode=latency` delays `/ready` and should trip the ALB p95 latency
  deployment alarm.

The drill enforces the app rollback objectives in
[Rollback Drill SLOs](rollback-drill-slos.md): error rollback observed within
10 minutes, latency rollback observed within 15 minutes, and restored app
verification within 2 minutes.

Use Terraform outputs and environment variables in examples:

```bash
export AWS_REGION="${AWS_REGION:-eu-central-1}"
export STACK_NAME="${STACK_NAME:-<stack-name>}"
```

## Before Rolling Back

Confirm the current service state:

```bash
aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw api_service_name)" \
  --region "$AWS_REGION" \
  --query 'services[0].{status:status,taskDefinition:taskDefinition,deployments:deployments[*].{status:status,taskDefinition:taskDefinition,rolloutState:rolloutState,running:runningCount,pending:pendingCount}}'
```

List recent active app task definition revisions:

```bash
aws ecs list-task-definitions \
  --family-prefix "${STACK_NAME}" \
  --status ACTIVE \
  --sort DESC \
  --max-items 10 \
  --region "$AWS_REGION"
```

Choose the most recent known-good revision from the list. Prefer the revision
that was healthy immediately before the bad deploy. If the deploy also advanced
schema phase or runtime flags, confirm the target revision is compatible with
the current database state before updating the service.

If the failing deploy came from GitHub Actions, download the recent
`release-evidence-*` artifacts and build an incident bundle before choosing the
rollback target:

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
```

Use `/tmp/aws-sdlc-containers-incident-evidence/incident-evidence.md` to line
up the bad image tag, task definition, alarm window, and the most recent
healthy release event.

## Roll Back The Service

Set the target revision explicitly:

```bash
PREVIOUS_TASK_DEFINITION_ARN="<previous-task-definition-arn>"
```

Update the service:

```bash
aws ecs update-service \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --service "$(terraform -chdir=infra/app output -raw api_service_name)" \
  --task-definition "$PREVIOUS_TASK_DEFINITION_ARN" \
  --force-new-deployment \
  --region "$AWS_REGION"
```

Wait for stabilization:

```bash
aws ecs wait services-stable \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw api_service_name)" \
  --region "$AWS_REGION"
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
    "$(terraform -chdir=infra/app output -raw api_unhealthy_targets_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw api_target_5xx_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw api_target_latency_alarm_name)" \
  --region "$AWS_REGION"

aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw api_service_name)" \
  --region "$AWS_REGION" \
  --query 'services[0].events[:10]'
```

The alarms return to `OK` after their next clean evaluation windows.

## After Recovery

Record the bad and restored task definition ARNs in the incident notes. Keep the
bad revision active until the failure is understood unless it contains a known
secret or security exposure.

If runtime flags were changed during the failed deploy, use `docs/deployment.md`
to return `WRITE_MODE` or `READ_MODE` to the last compatible value.

# App Service Incident

Use this runbook when the public API is failing because the app service is
unhealthy, returning target 5xxs, or exceeding the target latency alarm.

This runbook is for app-service incidents. If the safest recovery is to restore
the previous app revision, follow
[ECS Deploy Rollback](ecs-deploy-rollback.md).

Use Terraform outputs and environment variables in examples:

```bash
export AWS_REGION="${AWS_REGION:-eu-central-1}"
export STACK_NAME="${STACK_NAME:-<stack-name>}"
```

## Trigger

Start here when any of these conditions are true:

- clients or synthetic checks show `/health` or `/ready` failures
- the unhealthy-targets, target-5xx, or target-latency alarm from
  `terraform -chdir=infra/app output` is in `ALARM`

In practice, prefer the alarm names from `terraform -chdir=infra/app output`
instead of assuming the current stack name.

Interpret the signal this way:

- unhealthy targets: ALB cannot keep app tasks healthy
- target 5xx or latency: traffic reaches the app, but requests are failing or
  slowing down
- `/health` healthy but `/ready` failing: likely dependency readiness, not
  process liveness

For local dependency-readiness practice, use
[App Dependency Readiness Drill](../drills/app-dependency-readiness.md).

## First Checks

Confirm alarm and service state:

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
  --region "$AWS_REGION"
```

Check running and recently stopped tasks:

```bash
aws ecs list-tasks \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --service-name "$(terraform -chdir=infra/app output -raw api_service_name)" \
  --desired-status RUNNING \
  --region "$AWS_REGION"

aws ecs list-tasks \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --family "${STACK_NAME}" \
  --desired-status STOPPED \
  --region "$AWS_REGION"
```

Check logs and endpoints:

```bash
aws logs tail "/ecs/${STACK_NAME}/api" --since 30m --region "$AWS_REGION"
curl -i "https://$(terraform -chdir=infra/app output -raw api_fqdn)/health"
curl -i "https://$(terraform -chdir=infra/app output -raw api_fqdn)/ready"
```

If Grafana/Loki/Prometheus are reachable, inspect the same window in the `App
Overview` dashboard and corresponding logs:

```logql
{stack="<stack-name>", service="api"} |= "ERROR"
```

If you have downloaded recent `release-evidence-*` artifacts from GitHub
Actions, build an incident bundle first so deploy/apply/build evidence and
current runtime context sit in one place:

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
```

Read `/tmp/aws-sdlc-containers-incident-evidence/incident-evidence.md` before
branching into deeper console checks.

## Triage

Use the smallest explanation that fits the evidence:

- `/health` fails or tasks keep restarting: app boot, config, networking, or
  container problem
- `/health` stays `200` but `/ready` fails: dependency readiness problem,
  usually PgBouncer, RDS, credentials, or security groups
- alarms start immediately after a deploy: suspect the new app revision first
- high latency with stable tasks: suspect slow queries, pool saturation, or
  downstream AWS latency

If the symptom is primarily database pressure, continue with
[RDS Pressure](rds-pressure.md).

## Recovery

If the incident started right after a deploy, prefer restoring the previous
healthy app revision with
[ECS Deploy Rollback](ecs-deploy-rollback.md).

If the app revision did not change, restore the failing dependency or reduce
load before scaling or adding new infrastructure. This toolkit is intentionally
lean; do not add caches, queues, or extra runtime layers as a first response to
an unexplained symptom.

## Verify

Confirm the service stabilizes and alarms clear:

```bash
aws ecs wait services-stable \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw api_service_name)" \
  --region "$AWS_REGION"

curl -fsS "https://$(terraform -chdir=infra/app output -raw api_fqdn)/health"

aws cloudwatch describe-alarms \
  --alarm-names \
    "$(terraform -chdir=infra/app output -raw api_unhealthy_targets_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw api_target_5xx_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw api_target_latency_alarm_name)" \
  --region "$AWS_REGION"
```

# App Service Incident

Use this runbook when the public API is failing because the app service is
unhealthy, returning target 5xxs, or exceeding the target latency alarm.

This runbook is for app-service incidents. If the safest recovery is to restore
the previous app revision, follow
[ECS Deploy Rollback](ecs-deploy-rollback.md).

## Trigger

Start here when any of these conditions are true:

- `aws-sdlc-containers-app-unhealthy-targets` is in `ALARM`
- `aws-sdlc-containers-app-target-5xx` is in `ALARM`
- `aws-sdlc-containers-app-target-latency` is in `ALARM`
- clients or synthetic checks show `/health` or `/ready` failures

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
    "$(terraform -chdir=infra/app output -raw app_unhealthy_targets_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw app_target_5xx_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw app_target_latency_alarm_name)" \
  --region eu-central-1

aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw app_service_name)" \
  --region eu-central-1
```

Check running and recently stopped tasks:

```bash
aws ecs list-tasks \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --service-name "$(terraform -chdir=infra/app output -raw app_service_name)" \
  --desired-status RUNNING \
  --region eu-central-1

aws ecs list-tasks \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --family aws-sdlc-containers \
  --desired-status STOPPED \
  --region eu-central-1
```

Check logs and endpoints:

```bash
aws logs tail /ecs/aws-sdlc-containers/app --since 30m --region eu-central-1
curl -i "https://$(terraform -chdir=infra/app output -raw api_fqdn)/health"
curl -i "https://$(terraform -chdir=infra/app output -raw api_fqdn)/ready"
```

If Grafana/Loki/Prometheus are reachable, inspect the same window in the `App
Overview` dashboard and corresponding logs:

```logql
{stack="aws-sdlc-containers", service="app"} |= "ERROR"
```

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
  --services "$(terraform -chdir=infra/app output -raw app_service_name)" \
  --region eu-central-1

curl -fsS "https://$(terraform -chdir=infra/app output -raw api_fqdn)/health"

aws cloudwatch describe-alarms \
  --alarm-names \
    "$(terraform -chdir=infra/app output -raw app_unhealthy_targets_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw app_target_5xx_alarm_name)" \
    "$(terraform -chdir=infra/app output -raw app_target_latency_alarm_name)" \
  --region eu-central-1
```

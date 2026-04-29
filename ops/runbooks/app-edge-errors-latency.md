# App Edge Errors Or Latency

Use this runbook when either CloudWatch alarm is in `ALARM`:

- `aws-sdlc-containers-app-target-5xx`
- `aws-sdlc-containers-app-target-latency`

## What The Alarms Mean

The 5xx alarm watches the ALB target group's `AWS/ApplicationELB`
`HTTPCode_Target_5XX_Count` metric. It fires when the app returns at least one
5xx response through the ALB in a five-minute window.

The latency alarm watches `TargetResponseTime` p95. It fires when p95 target
response time is above two seconds for at least two out of three one-minute
evaluation periods.

Both alarms mean traffic is reaching the app target group. If targets are
unhealthy instead, use `ops/runbooks/app-service-unhealthy.md`.

## First Checks

Confirm alarm state:

```bash
aws cloudwatch describe-alarms \
  --alarm-names \
    "$(terraform -chdir=infra output -raw app_target_5xx_alarm_name)" \
    "$(terraform -chdir=infra output -raw app_target_latency_alarm_name)" \
  --region eu-central-1
```

Check recent app logs:

```bash
aws logs tail /ecs/aws-sdlc-containers/app \
  --since 30m \
  --region eu-central-1
```

Inspect ECS service events and task state:

```bash
aws ecs describe-services \
  --cluster "$(terraform -chdir=infra output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra output -raw app_service_name)" \
  --region eu-central-1

aws ecs list-tasks \
  --cluster "$(terraform -chdir=infra output -raw ecs_cluster_name)" \
  --service-name "$(terraform -chdir=infra output -raw app_service_name)" \
  --desired-status RUNNING \
  --region eu-central-1
```

Smoke the public API:

```bash
curl -fsS "https://$(terraform -chdir=infra output -raw api_fqdn)/health"
```

## Common Causes

- Recent app deploy introduced an exception path.
- Database queries are slow or blocked.
- PgBouncer pool is saturated.
- RDS CPU, connections, or storage are under pressure.
- Downstream AWS APIs are slow or unavailable.
- The app is receiving more traffic than its current task size can handle.

## Recovery

If the alarms started after a deploy, roll back to the previous healthy task
definition revision:

```bash
aws ecs update-service \
  --cluster "$(terraform -chdir=infra output -raw ecs_cluster_name)" \
  --service "$(terraform -chdir=infra output -raw app_service_name)" \
  --task-definition "<previous-task-definition-arn>" \
  --force-new-deployment \
  --region eu-central-1
```

If the app revision did not change, reduce load or restore database health
before scaling the task. This stack is intentionally lean; do not add caching or
new infrastructure until logs and metrics identify the bottleneck.

Confirm recovery:

```bash
aws ecs wait services-stable \
  --cluster "$(terraform -chdir=infra output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra output -raw app_service_name)" \
  --region eu-central-1

curl -fsS "https://$(terraform -chdir=infra output -raw api_fqdn)/health"
```

The alarms return to `OK` after the next clean evaluation windows.

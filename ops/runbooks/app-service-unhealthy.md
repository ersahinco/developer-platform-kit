# App Service Unhealthy

Use this runbook when the `aws-sdlc-containers-app-unhealthy-targets`
CloudWatch alarm is in `ALARM`.

## What The Alarm Means

The alarm watches the ALB target group's `AWS/ApplicationELB`
`UnHealthyHostCount` metric. It fires when one or more app targets are unhealthy
for at least two out of three one-minute evaluation periods.

This usually means the ALB cannot get a healthy `/health` response from the app
task, or the task is failing before it can serve traffic.

For a lower-severity dependency drill where `/health` stays healthy but
`/ready` fails, use
[App Dependency Readiness Drill](../drills/app-dependency-readiness.md).

## First Checks

Confirm the alarm:

```bash
aws cloudwatch describe-alarms \
  --alarm-names "$(terraform -chdir=infra output -raw app_unhealthy_targets_alarm_name)" \
  --region eu-central-1
```

Inspect the ECS service and recent events:

```bash
aws ecs describe-services \
  --cluster "$(terraform -chdir=infra output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra output -raw app_service_name)" \
  --region eu-central-1
```

List running and recently stopped app tasks:

```bash
aws ecs list-tasks \
  --cluster "$(terraform -chdir=infra output -raw ecs_cluster_name)" \
  --service-name "$(terraform -chdir=infra output -raw app_service_name)" \
  --desired-status RUNNING \
  --region eu-central-1

aws ecs list-tasks \
  --cluster "$(terraform -chdir=infra output -raw ecs_cluster_name)" \
  --family aws-sdlc-containers \
  --desired-status STOPPED \
  --region eu-central-1
```

Inspect app logs:

```bash
aws logs tail /ecs/aws-sdlc-containers/app \
  --since 30m \
  --region eu-central-1
```

Check the public health endpoint:

```bash
curl -i "https://$(terraform -chdir=infra output -raw api_fqdn)/health"
```

## Common Causes

- New task revision fails to start or crashes during boot.
- The app cannot connect to PgBouncer or RDS.
- PgBouncer sidecar is unhealthy or misconfigured.
- Security group changes prevent ALB-to-task traffic on port 8000.
- `/health` is returning a non-200 response.

## Recovery

If the alarm started after a deploy, roll the ECS service back to the previous
healthy task definition revision. Use `ops/runbooks/ecs-deploy-rollback.md` to
identify the previous revision and complete the rollback safely:

```bash
aws ecs update-service \
  --cluster "$(terraform -chdir=infra output -raw ecs_cluster_name)" \
  --service "$(terraform -chdir=infra output -raw app_service_name)" \
  --task-definition "<previous-task-definition-arn>" \
  --force-new-deployment \
  --region eu-central-1
```

Wait for the service to stabilize:

```bash
aws ecs wait services-stable \
  --cluster "$(terraform -chdir=infra output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra output -raw app_service_name)" \
  --region eu-central-1
```

Confirm the API is healthy:

```bash
curl -fsS "https://$(terraform -chdir=infra output -raw api_fqdn)/health"
```

The alarm returns to `OK` after the ALB target group reports no unhealthy app
targets for the next evaluation windows.

# Observability Plan

Prometheus, Loki, and Grafana are the preferred observability target for this
project. CloudWatch remains a useful AWS-native tradeoff, but it is not the
primary demo path.

## Current State

- Application liveness endpoint exists at `/health`.
- Application readiness endpoint exists at `/ready` and checks database
  connectivity separately from process liveness.
- Application metrics endpoint exists at `/metrics`.
- HTTP responses include an `X-Request-ID` header, preserving a caller-supplied
  value when present or generating one when absent.
- App and task logs are emitted through ECS and Docker.
- Terraform creates CloudWatch log groups for ECS workloads.
- Terraform creates a CloudWatch alarm for EventBridge Scheduler target
  delivery failures on the scheduled data export job.
- Terraform creates a CloudWatch Logs metric filter that counts successful data
  export manifest log lines.
- Terraform creates a CloudWatch alarm when no successful data export is
  observed for two daily evaluation windows.
- Terraform creates a CloudWatch alarm for unhealthy ALB targets behind the app
  service.
- Terraform creates CloudWatch alarms for app target 5xx responses and elevated
  target response time behind the ALB.
- Terraform creates CloudWatch alarms for RDS CPU, free storage, and database
  connection pressure.
- Terraform creates a CloudWatch alarm when the order events DLQ has visible
  messages.
- Local Prometheus, Loki, Promtail, and Grafana run through the optional
  `observability` Docker Compose profile.

## Local Stack

Start the app first, then start the observability profile:

```bash
docker compose build app
docker compose up -d app
make observability
```

Open:

| Tool | URL |
|---|---|
| App liveness | `http://localhost:8000/health` |
| App readiness | `http://localhost:8000/ready` |
| App metrics | `http://localhost:8000/metrics` |
| Prometheus | `http://localhost:9090` |
| Loki | `http://localhost:3100/ready` |
| Grafana | `http://localhost:3000` |

Grafana credentials default to `admin` / `admin` and can be overridden through
`.env`. The provisioned dashboard is `AWS SDLC Containers / App Overview`.

The local stack contains:

- Prometheus scraping the app `/metrics` endpoint.
- Loki storing local container logs.
- Promtail reading Docker container logs through the Docker socket.
- Grafana data sources and dashboard provisioning, including a readiness-failure
  stat for `/ready` 5xx responses.

Promtail requires read-only access to `/var/run/docker.sock`, so the
observability profile is opt-in and not started by default.

## AWS Extension

The first AWS-native signal is intentionally small: a CloudWatch alarm watches
`AWS/Scheduler` `TargetErrorCount` for the default schedule group, where the
stack currently has one scheduled job. Its runbook is
`ops/runbooks/data-export-job-failure.md`.
The data export job also emits a JSON manifest on success; a CloudWatch Logs
metric filter turns that log line into the custom
`aws-sdlc-containers/DataExport` `SuccessCount` metric. A freshness alarm uses
that metric and fires after two consecutive daily evaluation windows without a
successful export, which avoids paging on small schedule delays.

The app service health signal watches the ALB target group's
`UnHealthyHostCount` metric. Its runbook is
`ops/runbooks/app-service-unhealthy.md`.

The app edge symptom signals watch target-generated 5xx responses and p95 target
response time. Their runbook is `ops/runbooks/app-edge-errors-latency.md`.
The local Grafana dashboard also surfaces `/ready` 5xx responses separately so
operators can distinguish dependency-readiness symptoms from general request
traffic before following the app or RDS runbooks. Rehearse this path with
[App Dependency Readiness Drill](../ops/drills/app-dependency-readiness.md).

The RDS pressure signals watch `CPUUtilization`, `FreeStorageSpace`, and
`DatabaseConnections`. Their runbook is `ops/runbooks/rds-pressure.md`.

The async order event signal watches visible messages in the SQS DLQ for
`order.created.v1`. Its runbook is
`ops/runbooks/order-event-queue-failure.md`. The app also exposes
`order_events_publish_total` from `/metrics` so local operators can distinguish
successful, failed, and skipped publish attempts.

Future AWS observability slices can choose whether to deploy:

- Prometheus/Loki/Grafana on ECS for open-source control.
- Amazon Managed Grafana plus CloudWatch for lower operational overhead.
- CloudWatch-only for the smallest AWS footprint.

The default implementation path remains local Prometheus, Loki, and Grafana
first.

## Acceptance Criteria

- Prometheus target is healthy.
- Grafana dashboard loads from provisioning and includes the readiness-failure
  stat.
- Loki shows app logs.
- `/metrics` does not change `/health`, `/ready`, request ID propagation, or API
  behavior.
- Observability remains optional for the base app rollout.

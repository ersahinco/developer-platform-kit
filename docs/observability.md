# Observability Plan

Prometheus, Loki, Tempo, and Grafana are the preferred observability target for
this project. CloudWatch remains active for AWS-native logs and alarms while
the Grafana stack dual-runs.

Grafana intentionally uses Loki for workload logs, Prometheus for application
and observability-stack metrics, and Tempo for API traces. It does not provision
the CloudWatch datasource by default. Parity means app-owned signals are emitted
or shipped to both AWS-native and portable Grafana-stack backends where
practical; Grafana should not depend on CloudWatch queries to be useful.

## Current State

- Application liveness endpoint exists at `/health`.
- Application readiness endpoint exists at `/ready` and checks database
  connectivity separately from process liveness.
- Application metrics endpoint exists at `/metrics`.
- HTTP responses include an `X-Request-ID` header, preserving a caller-supplied
  value when present or generating one when absent.
- App and task logs are emitted through ECS and Docker.
- Successful `/health` and `/metrics` access logs are suppressed at the API
  logger because they are high-volume probe/scrape noise. Non-2xx responses
  still pass through.
- Terraform creates CloudWatch log groups for ECS workloads.
- ECS workloads can dual-ship logs through FireLens to CloudWatch Logs and the
  private Loki service when the optional observability stack is enabled.
- The API can emit OpenTelemetry traces over OTLP/HTTP to self-hosted Tempo.
- App and observability service metrics are scraped by Prometheus for Grafana.
  AWS-native ALB, RDS, SQS, Scheduler, and alarm-state metrics remain in
  CloudWatch unless an explicit metric fan-out is added.
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
- Local Prometheus, Loki, Tempo, Promtail, and Grafana run through the optional
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
| Tempo | `http://localhost:3200` |
| Grafana | `http://localhost:3000` |

Grafana credentials default to `admin` / `admin` and can be overridden through
`.env`. The provisioned dashboard is `AWS SDLC Containers / App Overview`.

The local stack contains:

- Prometheus scraping the app `/metrics` endpoint.
- Prometheus scraping its own runtime metrics and Loki runtime metrics, enabling
  upstream/community component dashboards when imported.
- Prometheus loading local app alert rules from
  `observability/prometheus/rules/`.
- Loki storing local container logs.
- Promtail reading Docker container logs through the Docker socket and applying
  the same `stack`, `environment`, `service`, and `container` labels used in
  AWS.
- Tempo storing local OTLP traces from the API when `OTEL_TRACES_ENABLED=true`.
- Grafana data sources and dashboard provisioning, including a readiness-failure
  stat for `/ready` 5xx responses.

Community Grafana dashboards are a good fit for standard components such as
Prometheus, Loki, and Grafana itself. When a community dashboard becomes part of
the project contract, commit the provisioned JSON under
`observability/grafana/dashboards/` and let the AWS stack reuse it.

Promtail requires read-only access to `/var/run/docker.sock`, so the
observability profile is opt-in and not started by default.

Distributed tracing uses OpenTelemetry in the API and self-hosted Tempo in both
local Compose and the optional ECS observability stack. X-Ray is intentionally
not part of this path.

## AWS Extension

The first AWS-native signal is intentionally small: a CloudWatch alarm watches
`AWS/Scheduler` `TargetErrorCount` for the default schedule group, where the
stack currently has one scheduled job. Its runbook is
[Data Export Job Failure](runbooks/data-export-job-failure.md).
The data export job also emits a JSON manifest on success; a CloudWatch Logs
metric filter turns that log line into the custom
`aws-sdlc-containers/DataExport` `SuccessCount` metric. A freshness alarm uses
that metric and fires after two consecutive daily evaluation windows without a
successful export, which avoids paging on small schedule delays.

The app service health signal watches the ALB target group's
`UnHealthyHostCount` metric. Its runbook is
[App Service Unhealthy](runbooks/app-service-unhealthy.md).

The app edge symptom signals watch target-generated 5xx responses and p95 target
response time. Their runbook is
[App Edge Errors Or Latency](runbooks/app-edge-errors-latency.md).
The local Grafana dashboard also surfaces `/ready` 5xx responses separately so
operators can distinguish dependency-readiness symptoms from general request
traffic before following the app or RDS runbooks. Rehearse this path with
[App Dependency Readiness Drill](drills/app-dependency-readiness.md).
Prometheus also loads local alert rules for readiness failures, app request 5xx
symptoms, and p95 request latency so the same `/metrics` contract can back local
Grafana-stack alerting before any CloudWatch app-level reduction.

The RDS pressure signals watch `CPUUtilization`, `FreeStorageSpace`, and
`DatabaseConnections`. Their runbook is [RDS Pressure](runbooks/rds-pressure.md).

The async order event signal watches visible messages in the SQS DLQ for
`order.created.v1`. Its runbook is
[Order Event Queue Failure](runbooks/order-event-queue-failure.md). The app also exposes
`order_events_publish_total` from `/metrics` so local operators can distinguish
successful, failed, and skipped publish attempts. Prometheus loads a local rule
for `order_events_publish_total{status="failed"}` to make publish failures part
of the local app observability contract.

## Optional ECS Grafana Stack

`infra/app` contains an opt-in ECS/Fargate Grafana, Loki, Tempo, and Prometheus stack.
It is app-owned, disabled by the variable default, and enabled for this sandbox
through `infra/app/stack.tfvars`. It reuses the local dashboard, datasource,
and Prometheus rule files from `observability/`.
AWS-specific templates under `infra/app/templates/observability/` adapt only
the parts that differ in ECS, such as Cloud Map service names and S3-backed
Loki/Tempo storage.

In ECS, Loki log chunks/index data and Tempo trace blocks use the existing
observability S3 bucket. Grafana provisioning assets are also loaded from that
bucket at task startup. Prometheus uses task-local TSDB storage in this sandbox;
durable S3-backed metrics would require adding a metrics store such as Thanos
or Mimir, not a Grafana CloudWatch datasource.

Enable it only after the app images have been pushed and the base app services
are healthy:

```bash
aws secretsmanager create-secret \
  --name aws-sdlc-containers/grafana-admin \
  --secret-string '<strong-password>' \
  --region eu-central-1

terraform -chdir=infra/app apply \
  -var-file=stack.tfvars
```

The stack is private inside the VPC. Use the SSM/ECS Exec Grafana tunnel:

```bash
make grafana-tunnel
```

Then open `http://localhost:3000`. Do not make Grafana public as the default.

The same Loki label contract is used locally and in AWS:

- `stack`: `aws-sdlc-containers`.
- `environment`: `local` or `aws`.
- `service`: app or workload name.
- `container`: container name.

AWS and local LogQL examples:

```logql
{stack="aws-sdlc-containers", service="app", container="app"}
```

```logql
{stack="aws-sdlc-containers", service="pgbouncer", container="pgbouncer"}
```

```logql
{stack="aws-sdlc-containers", service="data-export-job"}
```

```logql
{stack="aws-sdlc-containers"} |~ "(?i)error|exception|traceback|failed"
```

The Loki and Prometheus datasources are provisioned with Grafana-managed alert
editing disabled. Alert and ruler endpoints are not part of this sandbox
contract; use provisioned Prometheus rules and CloudWatch alarms instead.

## CloudWatch Reduction Rules

Do not reduce CloudWatch until the matching Grafana-stack signal has dual-run in
ECS. Keep these AWS/platform signals in CloudWatch:

- ALB target health.
- RDS CPU, storage, and connection pressure.
- EventBridge Scheduler delivery failures.
- SQS DLQ visibility while SQS remains the transport.
- CloudWatch logs for workload and observability diagnostics.

CloudWatch is the AWS-native break-glass path and remains the source of truth
for ALB, RDS, SQS, Scheduler, and CloudWatch alarm state. Grafana matches
workload log content through Loki and app metrics through Prometheus. When the
project needs the same app metric series in CloudWatch and Grafana, prefer an
OpenTelemetry Collector/ADOT fan-out that exports app metrics to CloudWatch
while Prometheus continues to serve Grafana; do not make Grafana portable
dashboards depend on the CloudWatch datasource.

Only these app-level CloudWatch surfaces have reduction toggles, and both
default to `true`:

| Variable | CloudWatch surface | Disable only after |
|---|---|---|
| `enable_app_symptom_cloudwatch_alarms` | ALB target 5xx and latency symptom alarms | Prometheus/Grafana app 5xx and latency alerts have dual-run through at least one deploy cycle. |
| `enable_data_export_success_cloudwatch_alarm` | Data-export success metric filter and freshness alarm | A Grafana-stack freshness signal from job metrics or Loki has dual-run. |

## Acceptance Criteria

- Prometheus target is healthy.
- Grafana dashboard loads from provisioning and includes the readiness-failure
  stat.
- Loki shows app logs.
- Tempo shows API traces.
- Prometheus loads local app alert rules.
- `/metrics` does not change `/health`, `/ready`, request ID propagation, or API
  behavior.
- Observability remains optional for the base app rollout.

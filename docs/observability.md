# Observability

The observability contract is local-first and portable. Prometheus, Loki, Tempo,
and Grafana remain the learning and dashboard surface under `observability/` and
Docker Compose. AWS ECS does not self-host that stack.

Cloud workloads keep only the runtime primitives they need:

- stdout/stderr logs go to CloudWatch Logs through the ECS `awslogs` driver.
- the API emits OTLP/HTTP traces to a same-task ADOT collector on
  `http://127.0.0.1:4318/v1/traces` when `enable_adot_sidecar = true`.
- the ADOT collector scrapes the app `/metrics` endpoint and can be reconfigured
  to export to any OTLP-compatible, Prometheus remote write, or provider-native
  backend.
- Grafana dashboards stay standard JSON and do not depend on a CloudWatch
  datasource or any cloud-only Grafana feature.
- CloudWatch alarms remain for AWS-native rollback and managed-resource signals.

This keeps the project goal intact: teams learn the standard tools without
carrying a Terraform implementation of every observability product.

## Local Stack

Start the local observability stack:

```bash
make observability
```

Start the app plus local observability:

```bash
make local-up
```

Local endpoints:

| Tool | Endpoint |
|---|---|
| Prometheus | `http://localhost:9090` |
| Loki | `http://127.0.0.1:3100/ready` |
| Tempo | `http://localhost:3200` |
| Grafana | `http://127.0.0.1:3000` |

Grafana defaults to `admin` / `admin` locally. Its provisioning lives under
`observability/grafana/`; dashboards are normal JSON files that can move to
Grafana OSS, Grafana Cloud, ECS, Kubernetes, or another managed service without
Terraform rewriting them.

## Cloud Runtime

The ECS app task has `app`, `pgbouncer`, and optional `adot` containers. There is
no ECS service for Grafana, Loki, Prometheus, or Tempo.

The Terraform contract lives in:

- `infra/app/observability.tf` for container defaults and the optional ADOT
  sidecar.
- `infra/app/edge_access_logs.tf` for the ALB access-log bucket.
- `infra/app/app_log_groups.tf` and `infra/app/workload_jobs.tf` for CloudWatch
  log groups.

The default ADOT config receives OTLP traces on ports `4317` and `4318`, scrapes
`127.0.0.1:8000/metrics`, and exports through the collector debug exporter to
its CloudWatch log group. Override `adot_collector_config` when you have a real
destination such as a local tunnel, a free-tier SaaS OTLP endpoint, Amazon
Managed Service for Prometheus, or another OpenTelemetry backend.

If the ADOT sidecar is disabled, set `otel_exporter_otlp_traces_endpoint` to send
API traces directly to an external OTLP/HTTP endpoint.

## Logs And Metrics

Cloud log groups:

| Log group | Writer | Freshness |
|---|---|---|
| `/ecs/aws-sdlc-containers/app` | API container | Always-on |
| `/ecs/aws-sdlc-containers/adot` | ADOT collector sidecar | Always-on when enabled |
| `/ecs/aws-sdlc-containers/pgbouncer` | PgBouncer sidecar | Always-on when app runs |
| `/ecs/aws-sdlc-containers/order-event-consumer` | Order event consumer, daprd, config loader | Always-on |
| `/ecs/aws-sdlc-containers/data-export-job` | Scheduled data export task | Batch |
| `/ecs/aws-sdlc-containers/liquibase` | Migration task | One-off |
| `/ecs/aws-sdlc-containers/worker` | Backfill worker task | One-off |

CloudWatch remains the source for:

| Namespace | Signal |
|---|---|
| `AWS/ApplicationELB` | `UnHealthyHostCount`, `HTTPCode_Target_5XX_Count`, `TargetResponseTime` |
| `AWS/RDS` | `CPUUtilization`, `FreeStorageSpace`, `DatabaseConnections` |
| `AWS/SQS` | `ApproximateNumberOfMessagesVisible` for the order event DLQ |
| `AWS/Scheduler` | `TargetErrorCount` for scheduled data export delivery |
| `aws-sdlc-containers/DataExport` | `SuccessCount` for successful data export freshness |
| `ECS/ContainerInsights` | ECS inspection and AWS-native troubleshooting |
| `AWS/WAFV2` | public edge security inspection |

Prometheus remains the portable metrics shape. The API and order event consumer
serve Prometheus text at `/metrics`; the local stack scrapes those endpoints.

## Traces

Tracing is OpenTelemetry first. The API has OTLP/HTTP tracing dependencies and
excludes `/health` and `/metrics` by default. The app service sets:

- `OTEL_TRACES_ENABLED=true`
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces`
- `OTEL_SERVICE_NAME=aws-sdlc-containers-api`
- `OTEL_DEPLOYMENT_ENVIRONMENT=aws`

for ECS when the ADOT sidecar is enabled. Local Compose sets
`OTEL_TRACES_ENABLED=true` for the local Tempo path.

## Release Evidence

Release and incident evidence stay portable:

- `scripts/observability/release_event.py` writes Markdown, JSON, and JSONL.
- cloud-changing workflows upload `release-evidence-*` artifacts.
- the same records can be pushed to Loki when `LOKI_PUSH_URL` or `LOKI_URL` is
  reachable.
- `scripts/observability/incident_evidence_bundle.py` builds operator-readable
  bundles with CloudWatch alarm snapshots, release event context, and
  Grafana-stack query hints.

Useful commands:

```bash
make incident-evidence
LOKI_URL=http://127.0.0.1:3100 make incident-evidence
LOKI_URL=http://127.0.0.1:3100 make release-event-delivery-verify
```

## Validation

Run the contract tests after changing observability wiring:

```bash
uv run pytest tests/contracts/test_observability_contract.py tests/scripts/test_observability_scripts.py -q
```

Run live delivery checks when cloud credentials or a reachable Loki endpoint are
available:

```bash
make observability-delivery-verify
LOKI_URL=http://127.0.0.1:3100 make observability-delivery-verify
```

The invariant is simple: AWS runs the workload and emits standard telemetry;
local or external observability tools analyze it.

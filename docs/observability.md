# Observability

The observability contract is portable and local-first:

- workloads emit Prometheus-compatible metrics
- workloads emit structured logs that can be read in CloudWatch or Loki
- the API can emit OTLP/HTTP traces
- Grafana dashboards stay normal JSON, not cloud-locked dashboard definitions
- CloudWatch remains the AWS-native signal plane for rollback alarms and managed
  resource symptoms

The goal is to keep standard telemetry shapes without hosting a full Grafana,
Loki, Prometheus, and Tempo platform inside AWS Terraform.

This doc owns observability behavior and operator workflow. Use
[Platform Contract](platform-contract.md#observability) for the portable
contract and [Platform Capabilities](platform-capabilities.md) for the current
capability inventory.

## Concern Profiles

Observability now follows the same concern/profile model as Dapr:

- `local` profile: the OSS stack under `platform/concerns/observability/`
- `aws` profile: CloudWatch logs, CloudWatch alarms, and optional ADOT sidecar
  wiring owned through Terraform and release/operator scripts

This keeps environment differences explicit without introducing a custom
observability abstraction layer.

## Local Runtime

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

Grafana provisioning lives under
`platform/concerns/observability/grafana/`.

## Cloud Runtime

AWS runs only the telemetry primitives needed by the workloads:

- CloudWatch Logs for container logs
- CloudWatch alarms for ALB, RDS, SQS, Scheduler, WAF, and rollback signals
- optional same-task ADOT collector for OTLP traces and `/metrics` scraping

There is no ECS service for Grafana, Loki, Prometheus, or Tempo.

Key Terraform ownership:

- `infra/app/observability.tf`: optional ADOT sidecar and app telemetry wiring
- `infra/app/edge_access_logs.tf`: ALB access-log bucket
- `infra/app/app_log_groups.tf` and `infra/app/workload_jobs.tf`: log groups

If `enable_adot_sidecar = true`, the API sends traces to the collector on
`http://127.0.0.1:4318/v1/traces`. If the sidecar is disabled, point
`otel_exporter_otlp_traces_endpoint` at an external OTLP/HTTP backend.

## Signals

Cloud log groups:

| Log group | Writer |
|---|---|
| `/ecs/<stack-name>/app` | edge-service container in the current reference runtime |
| `/ecs/<stack-name>/adot` | ADOT sidecar when enabled |
| `/ecs/<stack-name>/pgbouncer` | PgBouncer sidecar |
| `/ecs/<stack-name>/order-event-consumer` | Consumer, `daprd`, config loader |
| `/ecs/<stack-name>/data-export-job` | Scheduled export task |
| `/ecs/<stack-name>/liquibase` | Migration task |
| `/ecs/<stack-name>/worker` | Backfill worker |

CloudWatch owns these AWS-native signals:

| Namespace | Purpose |
|---|---|
| `AWS/ApplicationELB` | unhealthy targets, target 5xx, target latency |
| `AWS/RDS` | CPU, storage, connection pressure |
| `AWS/SQS` | order-event DLQ visibility |
| `AWS/Scheduler` | scheduled export delivery failures |
| `<stack-name>/DataExport` | export freshness |
| `ECS/ContainerInsights` | ECS troubleshooting |
| `AWS/WAFV2` | public edge security inspection |

Prometheus remains the portable app metrics shape. The API and order event
consumer expose `/metrics`; the local stack scrapes those endpoints.

## Alarm Ownership

Keep alarm categories explicit:

- platform-owned edge alarms: ALB health, 5xx, latency
- platform-owned managed-resource alarms: RDS, SQS, Scheduler, WAF
- workload-derived delivery alarms: alarms whose presence depends on declared
  workload capabilities such as Dapr event delivery or scheduled export runs
- release/incident default snapshots: the bounded alarm set collected by
  release and incident evidence scripts

The repo now centralizes default release and incident alarm inventories in
`scripts/observability/platform_inventory.py` so those inventories stay aligned
with the actual runtime contract instead of drifting into handwritten lists.

## Debug Loop

Use one correlation key per request, then follow it across the runtime:

- `X-Request-ID`: response headers, logs, traces
- `Idempotency-Key`: idempotency rows and replay behavior
- order id: orders, outbox, receipts, exports
- unique `billing_email`: DB rows and CSV exports
- image tag: ECR image, task definition, deploy evidence

Practical loop:

1. Send a request with `X-Request-ID`, `Idempotency-Key`, and a unique email.
2. Check app logs or Loki for that request.
3. Check traces if tracing is enabled.
4. Query Postgres for the order, idempotency record, outbox row, and receipt.
5. Inspect the export manifest or raw CSV when the symptom reaches the data hub.
6. Inspect ALB access logs for edge timing or status-code forensics.

For schema and storage flow, use [Data](data.md). For recovery paths, use
[Runbooks](runbooks/README.md).

## Release Evidence

Release and incident evidence stay portable:

- `scripts/observability/release_event.py` writes Markdown, JSON, and JSONL
- cloud-changing workflows upload `release-evidence-*` artifacts
- the same records can be pushed to Loki when a reachable endpoint exists
- `scripts/observability/incident_evidence_bundle.py` assembles incident bundles

Useful commands:

```bash
make incident-evidence
LOKI_URL=http://127.0.0.1:3100 make incident-evidence
make release-event-delivery-verify
LOKI_URL=http://127.0.0.1:3100 make release-event-delivery-verify
```

## Validation

After changing observability wiring:

```bash
uv run pytest tests/contracts/test_observability_contract.py tests/scripts/test_observability_scripts.py -q
```

When cloud credentials or Loki are reachable:

```bash
make observability-delivery-verify
LOKI_URL=http://127.0.0.1:3100 make observability-delivery-verify
```

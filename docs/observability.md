# Observability

Canonical observability behavior and operator loop.

Use [Platform Contract](platform-contract.md#observability) for portable
workload rules and [Platform Capabilities](platform-capabilities.md) for the
current capability map.

## Contract

- workloads emit Prometheus-compatible metrics
- workloads emit structured logs readable in CloudWatch or Loki
- the API can emit OTLP/HTTP traces
- Grafana dashboards stay normal JSON
- CloudWatch remains the AWS-native signal plane for rollback alarms and
  managed-resource symptoms

Goal: keep standard telemetry shapes without hosting Grafana, Loki,
Prometheus, and Tempo inside AWS Terraform.

## Profiles

| Profile | Owner |
|---|---|
| `local` | OSS stack under `platform/concerns/observability/` |
| `aws` | CloudWatch logs, CloudWatch alarms, optional ADOT sidecar, release/operator scripts |

## Local Runtime

```bash
make observability
make local-up
```

| Tool | Endpoint |
|---|---|
| Prometheus | `http://localhost:9090` |
| Loki | `http://127.0.0.1:3100/ready` |
| Tempo | `http://localhost:3200` |
| Grafana | `http://127.0.0.1:3000` |

Grafana provisioning lives under `platform/concerns/observability/grafana/`.

## AWS Runtime

AWS runs only workload-facing telemetry primitives:

- CloudWatch Logs for container logs
- CloudWatch alarms for ALB, RDS, SQS, Scheduler, WAF, and rollback signals
- optional same-task ADOT collector for OTLP traces and `/metrics` scraping

There is no ECS service for Grafana, Loki, Prometheus, or Tempo.

Terraform ownership:

- `infra/app/observability.tf`
- `infra/app/edge_access_logs.tf`
- `infra/app/app_log_groups.tf`
- `infra/app/workload_jobs.tf`

If `enable_adot_sidecar = true`, the API sends traces to
`http://127.0.0.1:4318/v1/traces`. Otherwise point
`otel_exporter_otlp_traces_endpoint` at an external OTLP/HTTP backend.

## Signals

Cloud log groups:

| Log group | Writer |
|---|---|
| `/ecs/<stack-name>/api` | edge-service container |
| `/ecs/<stack-name>/adot` | ADOT sidecar when enabled |
| `/ecs/<stack-name>/pgbouncer` | PgBouncer sidecar |
| `/ecs/<stack-name>/order-event-consumer` | consumer, `daprd`, config loader |
| `/ecs/<stack-name>/data-export-job` | scheduled export task |
| `/ecs/<stack-name>/liquibase` | migration task |
| `/ecs/<stack-name>/backfill-worker` | backfill worker |

CloudWatch namespaces:

| Namespace | Purpose |
|---|---|
| `AWS/ApplicationELB` | unhealthy targets, target 5xx, target latency |
| `AWS/RDS` | CPU, storage, connection pressure |
| `AWS/SQS` | order-event DLQ visibility |
| `AWS/Scheduler` | scheduled export delivery failures |
| `<stack-name>/DataExport` | export freshness |
| `ECS/ContainerInsights` | ECS troubleshooting |
| `AWS/WAFV2` | public edge security inspection |

Prometheus remains the portable app metrics shape.

## Alarm Ownership

- platform-owned edge alarms: ALB health, 5xx, latency
- platform-owned managed-resource alarms: RDS, SQS, Scheduler, WAF
- workload-derived delivery alarms: alarms derived from workload capabilities
- release/incident default snapshots: bounded alarm sets collected by evidence
  scripts

Default release and incident alarm inventories live in
`scripts/observability/platform_inventory.py`.

## Debug Loop

Use one correlation key, then follow it:

- `X-Request-ID`
- `Idempotency-Key`
- order id
- unique `billing_email`
- image tag

Path:

1. Send a request with `X-Request-ID`, `Idempotency-Key`, and a unique email.
2. Check app logs or Loki.
3. Check traces if enabled.
4. Query Postgres for the order, idempotency record, outbox row, and receipt.
5. Inspect the export manifest or raw CSV if the symptom reaches the data hub.
6. Inspect ALB access logs for edge timing or status-code forensics.

Use [Data](data.md) for schema and storage flow and
[Runbooks](runbooks/README.md) for recovery paths.

## Evidence Commands

```bash
make incident-evidence
LOKI_URL=http://127.0.0.1:3100 make incident-evidence
make release-event-delivery-verify
LOKI_URL=http://127.0.0.1:3100 make release-event-delivery-verify
```

Release and incident evidence is produced by:

- `scripts/observability/release_event.py`
- `scripts/observability/incident_evidence_bundle.py`

## Validation

```bash
uv run pytest tests/contracts/test_observability_contract.py tests/scripts/test_observability_scripts.py -q
```

When cloud credentials or Loki are reachable:

```bash
make observability-delivery-verify
LOKI_URL=http://127.0.0.1:3100 make observability-delivery-verify
```

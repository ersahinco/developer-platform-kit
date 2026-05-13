# Operator Observability Map

This is the practical map for following one application change from a developer
machine through AWS edge, ECS workloads, Postgres, S3, and downstream delivery.
It is intentionally smaller than a full architecture document: use it when you
need to build, debug, iterate, and prove where one piece of data went.

## Mental Model

```text
developer request
  -> public ALB + WAF
  -> ECS app task
     -> app container
     -> pgbouncer sidecar
     -> ADOT sidecar for OTLP traces and app metric scraping
  -> RDS Postgres
     -> transactional order data
     -> runtime rollout switches
     -> durable outbox and idempotency state
  -> order-event-consumer ECS service
     -> Dapr sidecar
     -> SNS FIFO topic + SQS FIFO queue + DLQ
     -> order_event_receipts table
  -> data-export-job scheduled ECS task
     -> data hub S3 raw CSV
     -> data hub S3 manifest JSON
```

For local-to-AWS tracing, always send your own identifiers:

- `X-Request-ID`: follows HTTP responses, app log context, and traces; metrics
  remain aggregate by route/status.
- `Idempotency-Key`: persists in Postgres and appears in order event payloads.
- A unique `billing_email`: makes the row easy to find in the database export.

## Persistence Inventory

### Data Hub Bucket

Bucket: `arn:aws:s3:::aws-sdlc-containers-data-hub-691627364817`

This is app-owned data output. Runtime code writes here; Terraform owns only the
bucket guardrails.

| Prefix | Format | Writer | Meaning | How to read |
|---|---|---|---|---|
| `raw/order_contact_email/dt=<YYYY-MM-DD>/<run-id>.csv` | CSV | `data-export-job` | Snapshot of `order_contact_email` ordered by `order_id`. | `aws s3 cp s3://.../raw/... -` |
| `manifests/order_contact_email/dt=<YYYY-MM-DD>/<run-id>.json` | JSON | `data-export-job` | Success signal for the matching raw CSV, including row count, byte count, SHA-256, run id, and object keys. | `aws s3 cp s3://.../manifests/... - | jq .` |
| `curated/` | reserved | none today | Future promoted datasets. | No object expected in v1. |

Critical notes:

- The manifest is the downstream-ready signal. Treat a raw CSV without a
  manifest as incomplete until proven otherwise.
- The job uploads raw before manifest. If raw upload fails, no manifest should be
  uploaded.
- Versioning is enabled, but noncurrent versions expire after 7 days. Do not use
  this bucket as an audit log.

### ALB Access Logs Bucket

Bucket: `arn:aws:s3:::aws-sdlc-containers-observability-691627364817`

This bucket is now owned by the ALB access-log path. The name is retained from
the retired observability stack to avoid replacing deployed log storage.

| Prefix/object class | Format | Writer | Meaning | How to read |
|---|---|---|---|---|
| `alb-access-logs/AWSLogs/.../*.log.gz` | gzip text | ALB log delivery | Edge request records: client, target, timings, status codes, request line, user agent, TLS, routing, errors. | `aws s3 cp s3://...log.gz - | gzip -dc` |
| `alb-access-logs/AWSLogs/.../ELBAccessLogTestFile` | text test file | AWS | Delivery permission test, not traffic. | Usually ignore. |
| `config/loki/loki.yml` | YAML | Terraform | Deployed Loki config. | `aws s3 cp s3://.../config/loki/loki.yml -` |
| `config/prometheus/prometheus.yml` | YAML | Terraform | Deployed Prometheus scrape config. | `aws s3 cp s3://.../config/prometheus/prometheus.yml -` |
| `config/prometheus/rules/app-alerts.yml` | YAML | Terraform | App alert rules loaded by Prometheus. | `aws s3 cp s3://.../config/prometheus/rules/app-alerts.yml -` |
| `config/grafana/...` | YAML/JSON | Terraform | Grafana datasources, dashboard provisioning, dashboards. | `aws s3 cp s3://.../config/grafana/... -` |
| Loki chunk/index objects such as `fake/<fingerprint>/<chunk-id>` | Loki TSDB/chunk internals, Snappy-compressed | Loki | Stored log streams. Example labels include `service=pgbouncer`, `container=pgbouncer`, `stack=aws-sdlc-containers`. | Query Loki/Grafana; do not read objects directly. |
| `tempo/...` | Tempo block internals | Tempo | Stored trace blocks. | Query Tempo/Grafana; do not read objects directly. |

Critical notes:

- ALB access logs are the edge truth, but they are delayed and file-oriented.
  Use them for forensic edge debugging, not fast inner-loop iteration.
- Loki and Tempo objects are backend storage, not an operator interface. Query
  them through Grafana, Loki API, or Tempo API.
- This bucket also stores config used at task startup. A bad config object can
  break the observability task that reads it.

### Runtime Config Bucket

There is also a generated runtime-config bucket:
`aws-sdlc-containers-runtime-config-691627364817`.

It is not one of the two buckets above, but it is part of persistence because
the Dapr sidecars load SNS/SQS component config from it at startup:

```text
config/dapr/order-events/
|-- components/order-events-pubsub.yaml
|-- components/resiliency.yaml
`-- config/config.yaml
```

## Database Tables

| Table | Owner | Role in flow | Main read/write paths |
|---|---|---|---|
| `customers` | API/Liquibase seed and fixture endpoint | Validates `POST /orders` customer existence. | API reads; `/admin/observability-fixture` inserts when needed. |
| `orders` | API | Primary order record. During the migration exercise, `billing_email` is legacy storage. | `POST /orders` writes; `GET /orders/{id}` reads according to `READ_MODE`. |
| `order_contact_email` | API/backfill/export | New home for billing email. | API writes in `dual` or `new`; backfill inserts historical rows; data export reads. |
| `app_runtime_config` | API/admin rollout operations | Runtime switches: `WRITE_MODE` and `READ_MODE`. | API reads with a short TTL cache; admin endpoints update. |
| `backfill_progress` | backfill worker | Checkpoint for `order_contact_email_backfill`. | Worker reads and updates per batch. |
| `outbox_messages` | API/order-event-consumer | Durable transactional outbox for `order.created.v1`. | API inserts in the same DB transaction as order creation; relay marks pending/processing/published. |
| `idempotency_keys` | API | Stores `POST /orders` in-flight and completed responses. | API begins, completes, replays, or fails by `Idempotency-Key`. |
| `order_event_receipts` | order-event-consumer | Durable record of consumed order events, duplicates, and stale events. | Consumer inserts or increments duplicate count. |
| `databasechangelog`, `databasechangeloglock` | Liquibase | Migration history and lock state. | Liquibase only. |

Critical notes:

- API traffic goes through PgBouncer; Liquibase, backfill, and data export
  connect directly to Postgres because they need stable or long-running
  sessions.
- `outbox_messages` is the handoff point from synchronous API work to async
  delivery. If an order exists but downstream did not see it, inspect outbox
  status first.
- `order_contact_email` is the dataset boundary for exports. If a billing email
  is not there, it cannot appear in the data hub raw CSV.

## Data Flows

### Create and Observe One Order

Use a unique request id, idempotency key, and email:

```bash
REQ_ID="local-$(date -u +%Y%m%dT%H%M%SZ)"
IDEMPOTENCY_KEY="$REQ_ID-order"
EMAIL="$REQ_ID@example.test"

curl --fail --show-error \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $REQ_ID" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -d "{\"customer_id\":1,\"total_amount\":\"12.34\",\"billing_email\":\"$EMAIL\"}" \
  "$API_BASE_URL/orders"
```

Then follow it:

1. ALB edge: find the request in ALB access logs by timestamp, path, status, and
   target response time.
2. App logs: search CloudWatch or Loki for `$REQ_ID`, `POST /orders`, or the
   returned order id.
3. Traces: search Tempo by service `aws-sdlc-containers-api` and the request
   time window.
4. Database: find the order, idempotency row, and outbox message.
5. Async relay: check `order-event-consumer` logs for `outbox_relay`.
6. Consumption: check `order_event_receipts` and `order_event_consumed` logs.
7. Export: run or wait for `data-export-job`, then inspect the manifest and raw
   CSV in the data hub bucket.

Useful database checks:

```sql
SELECT key, status, response_status_code, updated_at
FROM idempotency_keys
WHERE key = '<Idempotency-Key>';

SELECT id, customer_id, total_amount, status, billing_email, submitted_at
FROM orders
WHERE id = <order-id>;

SELECT order_id, billing_email, source, updated_at
FROM order_contact_email
WHERE order_id = <order-id>;

SELECT id, event_type, event_id, aggregate_id, status, attempt_count, last_error
FROM outbox_messages
WHERE aggregate_type = 'order' AND aggregate_id = <order-id>;

SELECT event_id, event_type, aggregate_id, status, duplicate_count, last_seen_at
FROM order_event_receipts
WHERE aggregate_type = 'order' AND aggregate_id = <order-id>;
```

### Backfill Flow

```text
worker task
  -> SELECT old rows from orders where id > backfill_progress.last_order_id
  -> INSERT missing order_contact_email rows with source='backfill'
  -> UPDATE backfill_progress checkpoint
  -> emit JSON progress logs
```

Observe it with:

- CloudWatch/Loki log group: `/ecs/aws-sdlc-containers/worker`.
- DB checkpoint: `SELECT * FROM backfill_progress;`.
- Target table count: `SELECT count(*) FROM order_contact_email;`.

Critical note: the worker reports progress only while it has batches. An old log
stream is normal between one-off backfill runs.

### Data Export Flow

```text
data-export-job
  -> SELECT order_contact_email ORDER BY order_id
  -> write local /tmp raw CSV
  -> calculate byte count and SHA-256
  -> write success manifest JSON
  -> upload raw to data hub S3
  -> upload manifest to data hub S3
  -> print manifest JSON to logs
```

Observe it with:

```bash
aws s3 ls \
  s3://aws-sdlc-containers-data-hub-691627364817/manifests/order_contact_email/ \
  --recursive

aws s3 cp s3://aws-sdlc-containers-data-hub-691627364817/<manifest-key> - | jq .
```

Critical note: the CloudWatch success metric is derived from the manifest JSON
printed by the job. If the manifest object exists but the alarm still fires,
inspect `/ecs/aws-sdlc-containers/data-export-job` log delivery and metric
filter matching.

## Logs and Metrics Contract

Think of an ECS task as the closest AWS equivalent of a Kubernetes pod. Each
task definition may contain multiple containers; useful defaults need visibility
at service, task, and container levels.

### Logs

| Runtime | Containers | Default log surface |
|---|---|---|
| App service task | `app`, `pgbouncer`, optional `adot` | CloudWatch `/ecs/aws-sdlc-containers/app`, `/ecs/aws-sdlc-containers/pgbouncer`, `/ecs/aws-sdlc-containers/adot`; ADOT receives OTLP traces on localhost and scrapes `/metrics`. |
| Order event consumer task | `order-event-consumer`, `daprd`, `dapr-config-loader` | CloudWatch `/ecs/aws-sdlc-containers/order-event-consumer`. |
| Data export job task | `data-export-job` | CloudWatch `/ecs/aws-sdlc-containers/data-export-job`. |
| Worker task | `worker` | CloudWatch `/ecs/aws-sdlc-containers/worker`. |
| Liquibase task | `liquibase` | CloudWatch `/ecs/aws-sdlc-containers/liquibase`. |

Desired default: every essential workload container emits to CloudWatch from the
first deploy. Loki remains a local or external analysis destination when logs
are shipped there outside Terraform.

### Metrics

| Metric class | Current backend | Current Grafana usability | Critical gap |
|---|---|---|---|
| API request count/latency | Prometheus scrape of app `/metrics` | Good for app-level iteration. | No per-route business metric for order creation/export yet. |
| Readiness/liveness | ALB/ECS health checks plus app `/ready` and `/health` | Good for app dependency symptoms. | Health check success logs are intentionally suppressed. |
| App/container CPU and memory | ECS/ContainerInsights in CloudWatch | Not first-class in Grafana because there is no CloudWatch datasource by default. | Need Prometheus ECS/container exporter or Grafana CloudWatch datasource if per-task CPU/memory must be in Grafana. |
| ALB/WAF/RDS/SQS/Scheduler | CloudWatch metrics and alarms | Not in Grafana by default. | This is deliberate today; add a metrics bridge only when the operator path needs it. |
| Local Grafana stack components | Prometheus scrapes Prometheus, Loki, and Tempo runtime metrics | Good for local observability health. | Cloud resource metrics stay CloudWatch-native until a metrics bridge is needed. |
| Data export freshness | CloudWatch Logs metric filter and alarm | Partial through logs. | Durable Grafana freshness needs a job metric or Loki ruler path. |

Critical evaluation:

- Logs are deliberately simple. CloudWatch is the AWS runtime surface;
  Loki/Grafana is the portable local or external operator view.
- Metrics are intentionally split. Prometheus covers app-owned and
  local observability metrics; CloudWatch covers managed AWS services and ECS
  resource metrics. This is pragmatic, but it means Grafana is not yet a single
  pane for service/task/container resource usage.
- The next highest-value metric improvement is not a giant dashboard. It is a
  small set of business and job metrics: orders created, outbox published/failed,
  order events consumed/failed, data export rows/bytes/success age, and
  backfill rows processed.

## Local to AWS Debug Loop

Use this shortest useful loop:

1. Build and test locally.
2. Run local app and observability profile.
3. Send a request with `X-Request-ID` and `Idempotency-Key`.
4. Confirm local DB rows and local Loki/Grafana logs.
5. Build/push immutable SHA image through CI.
6. Deploy the app task definition revision.
7. Send the same kind of request to the AWS ALB.
8. Check AWS app logs, local or external Loki logs when configured, Tempo trace,
   and DB rows.
9. Check outbox relay and consumer receipt.
10. Run or wait for export, then read manifest and raw object from S3.

Fast verification commands:

```bash
make observability-delivery-verify

LOKI_URL=http://127.0.0.1:3100 make observability-delivery-verify

make observability-cloud-traffic
```

No-data rollback practice:

- App: run the GitHub Actions workflow `App No-Data Rollback Drill`; it deploys
  only the app ECS service revision with `/ready` fault injection enabled.
  ECS circuit breaker and deployment CloudWatch alarms must roll it back
  automatically to the captured previous task definition.
- Other ECS services: order-event-consumer uses ECS deployment circuit breaker
  rollback for deployments that cannot stabilize.
  One-off tasks such as Liquibase, backfill, and data export are not ECS service
  rollouts, so practice their recovery with rerun/stop/restore runbooks instead
  of service rollback.
- Infra: use [Infra Rollback Drill](runbooks/infra-rollback-drill.md); it uses a
  reversible infra-only commit and its revert through the normal
  `Infra Plan`/`Infra Apply` path.

## What Good Looks Like

For a single order request, you should be able to answer these without guessing:

- Did the ALB receive it?
- Which app task handled it?
- Did the app commit the order?
- Which table contains the email for the current rollout mode?
- Was the idempotency key completed or replayed?
- Was an outbox message created and published?
- Did the downstream consumer record the event?
- Did the export job include the new row?
- Which S3 manifest proves the export completed?

If any answer requires reading raw Loki chunk objects or manually correlating
opaque task IDs from several consoles, the operator experience needs another
small improvement.

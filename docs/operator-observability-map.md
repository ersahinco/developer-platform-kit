# Operator Observability Map

Use this map to follow one application change across the current AWS/ECS
runtime. It is intentionally a correlation guide, not another architecture doc.
For durable design context, use [Architecture](architecture.md), [Data](data.md),
and [Observability](observability.md).

## Correlation Keys

Always create or capture these when debugging one request:

| Key | Where it appears |
|---|---|
| `X-Request-ID` | HTTP response headers, app logs, and traces. |
| `Idempotency-Key` | `idempotency_keys`, outbox payloads, and replay behavior. |
| Order id | `orders`, `order_contact_email`, `outbox_messages`, receipts, logs, and exports. |
| Unique `billing_email` | Easy lookup in DB rows and exported CSV data. |
| Image tag | ECR image, task definition revision, deploy evidence, rollback drills. |

## Runtime Surfaces

| Surface | Current source | Use it for |
|---|---|---|
| Edge access | ALB access logs in `<stack-name>-observability-<account-id>` | Delayed forensic edge truth: status, timings, target, TLS, user agent. |
| App logs | CloudWatch `/ecs/<stack-name>/app`; Loki when shipped there | Request and runtime-mode behavior. |
| Traces | API OTLP to ADOT sidecar, then configured backend | API and SQL hop timing. |
| Metrics | Prometheus for app/local stack; CloudWatch for AWS managed services | App request trends, rollback alarms, AWS resource symptoms. |
| Database | Postgres tables owned by Liquibase and app code | Committed state, rollout switches, idempotency, outbox, receipts. |
| Data hub | `<stack-name>-data-hub-<account-id>` | Raw CSV and manifest JSON from `data-export-job`. |
| Release evidence | Workflow artifacts; optional Loki push | Deploy, rollback drill, infra apply, and incident context. |

## Flow Map

```text
request
  -> ALB/WAF
  -> ECS app task: app + pgbouncer + optional ADOT
  -> Postgres: orders, runtime config, idempotency, outbox
  -> order-event-consumer: Dapr + SNS/SQS + receipts
  -> data-export-job: S3 raw CSV + manifest
```

The important handoff points are:

| Handoff | Proof |
|---|---|
| HTTP accepted | ALB log, app log, response request id. |
| Order committed | `orders` row and completed `idempotency_keys` row. |
| New email model written | `order_contact_email` row. |
| Async event emitted | `outbox_messages.status` and consumer logs. |
| Async event consumed | `order_event_receipts` row. |
| Data exported | Manifest object plus data export success log/metric. |

## One Request Debug Loop

1. Send a request with `X-Request-ID`, `Idempotency-Key`, and a unique email.
2. Check app logs or Loki for the request id and route.
3. Check Tempo for the same time window when tracing is enabled.
4. Query Postgres for the order, idempotency key, contact email, outbox message,
   and receipt.
5. Run or wait for `data-export-job`; read the manifest and raw CSV from the data
   hub bucket.
6. If the symptom is edge latency or status code, inspect ALB access logs.

Useful SQL:

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

Useful commands:

```bash
make observability-delivery-verify
LOKI_URL=http://127.0.0.1:3100 make observability-delivery-verify
make observability-cloud-traffic

aws s3 ls \
  s3://<stack-name>-data-hub-<account-id>/manifests/order_contact_email/ \
  --recursive
```

## Known Gaps

- Grafana is not a single pane for AWS managed-service metrics. CloudWatch owns
  ALB, RDS, SQS, Scheduler, WAF, and rollback alarms until a deliberate metrics
  bridge is added.
- ALB access logs are delayed and file-oriented; use them for forensics, not the
  fast inner loop.
- One-off task recovery is rerun/stop/forward-fix oriented. ECS service rollback
  semantics apply to long-running services, not completed jobs.

## Good Outcome

For one order request, an operator should be able to answer:

- Did the edge receive it?
- Which app task handled it?
- Did the database commit it?
- Was an outbox message published and consumed?
- Did the export include it?
- Which deploy or rollback event was active at the time?

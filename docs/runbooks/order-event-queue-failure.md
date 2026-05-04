# Order Event Queue Failure

Use this runbook when the `aws-sdlc-containers-order-events-dlq-visible`
CloudWatch alarm is in `ALARM`, or when consumer logs show failed
`order.created.v1` relay or consume attempts.

## What The Alarm Means

The order event consumer service relays `order.created.v1` messages from the
database outbox to the SQS FIFO queue named
`aws-sdlc-containers-order-events.fifo`, then consumes deliveries into
`order_event_receipts`.
Each message uses:

- `event_id`: `order.created.v1:<order_id>`
- `idempotency_key`: `order.created.v1:<order_id>`
- FIFO `MessageDeduplicationId`: same as `event_id`
- FIFO `MessageGroupId`: `customer-<customer_id>`

The DLQ alarm watches `AWS/SQS` `ApproximateNumberOfMessagesVisible` for
`aws-sdlc-containers-order-events-dlq.fifo`. It fires when any message is
visible in the DLQ.

## First Checks

Confirm the alarm:

```bash
aws cloudwatch describe-alarms \
  --alarm-names "$(terraform -chdir=infra/app output -raw order_events_dlq_visible_alarm_name)" \
  --region eu-central-1
```

Inspect the source queue and DLQ:

```bash
aws sqs get-queue-attributes \
  --queue-url "$(terraform -chdir=infra/app output -raw order_events_queue_url)" \
  --attribute-names All \
  --region eu-central-1

DLQ_URL="$(aws sqs get-queue-url \
  --queue-name "$(terraform -chdir=infra/app output -raw order_events_dlq_name)" \
  --query QueueUrl \
  --output text \
  --region eu-central-1)"

aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names All \
  --region eu-central-1
```

Inspect app and consumer logs:

```bash
aws logs tail /ecs/aws-sdlc-containers/app \
  --since 30m \
  --region eu-central-1

aws logs tail /ecs/aws-sdlc-containers/order-event-consumer \
  --since 30m \
  --region eu-central-1
```

## Grafana-Stack Checks

When the optional Grafana stack is enabled and reachable, check the provisioned
`App Overview` dashboard for `order_events_publish_total` outcomes. The matching
Prometheus alert is `OrderEventPublishFailures`.

Use Loki for app and consumer log context during the same window:

```logql
{stack="aws-sdlc-containers", service="app"} |= "order_event_publish_failed"
```

```logql
{stack="aws-sdlc-containers", service="order-event-consumer"}
```

Keep the SQS DLQ CloudWatch alarm in the flow until the later messaging
roadmap sessions replace SQS or provide an equivalent parking-stream signal.

## Common Causes

- A downstream queue consumer failed the same message five times.
- A deploy changed event payload handling without preserving idempotency.
- The order event consumer task role lost SQS permissions on the source queue.
- `ORDER_EVENTS_QUEUE_URL` points at the wrong queue.
- AWS SQS API calls from the private task cannot reach SQS through NAT or VPC
  endpoints.

## Recovery

If the worker cannot relay or consume order events, first restore queue access:

```bash
aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw app_service_name)" \
  --region eu-central-1

aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw order_event_consumer_service_name)" \
  --region eu-central-1
```

If the failure started after a deploy, use
[ECS Deploy Rollback](ecs-deploy-rollback.md) to restore the previous healthy
task definition.

Order creation is still allowed when relay fails because events remain durable
in `outbox_messages`. After the queue path is healthy, the relay should publish
pending rows without reconstructing events manually.

For DLQ messages, inspect before replaying:

```bash
aws sqs receive-message \
  --queue-url "$DLQ_URL" \
  --max-number-of-messages 10 \
  --attribute-names All \
  --message-attribute-names All \
  --visibility-timeout 30 \
  --region eu-central-1
```

Only replay messages after the consumer defect is fixed. Preserve the original
`event_id` and `idempotency_key`; consumers must treat those as the duplicate
detection key.

## Success Criteria

- Consumer logs contain `outbox_relay` entries only when messages are published
  or fail, and `order_event_consumed` entries when messages are consumed.
- `outbox_messages` rows move from `pending` or `processing` to `published`.
- `order_event_receipts` records the consumed `event_id`.
- The DLQ has zero visible messages.
- The CloudWatch alarm returns to `OK`.

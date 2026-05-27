# Event Consumer Queue Failure

Use this runbook when the async-events-dlq-visible CloudWatch alarm is in
`ALARM`, or when consumer logs show failed
relay or consume attempts for the current async event flow.

Use Terraform outputs and environment variables in examples:

```bash
export AWS_REGION="${AWS_REGION:-eu-central-1}"
export STACK_NAME="${STACK_NAME:-<stack-name>}"
```

## What The Alarm Means

The Dapr-enabled event consumer relays domain events from the outbox through
the `async-events-pubsub` component. In AWS that maps to SNS FIFO plus SQS
FIFO and ends in `event_receipts`.

The current bespoke workload publishes `order.created.v1`, so examples below
use that event type and its current payload shape.

Each message uses:

- `event_id`: `order.created.v1:<order_id>`
- `idempotency_key`: `order.created.v1:<order_id>`
- Dapr CloudEvent `id`: same as `event_id`
- Dapr CloudEvent `data`: the current domain event payload

The DLQ alarm watches `AWS/SQS` `ApproximateNumberOfMessagesVisible` for the
DLQ. It fires when any message is visible there.

## First Checks

Confirm the alarm:

```bash
aws cloudwatch describe-alarms \
  --alarm-names "$(terraform -chdir=infra/app output -raw async_eventing_dlq_visible_alarm_name)" \
  --region "$AWS_REGION"
```

Inspect the source queue and DLQ:

```bash
aws sqs get-queue-attributes \
  --queue-url "$(terraform -chdir=infra/app output -raw async_eventing_queue_url)" \
  --attribute-names All \
  --region "$AWS_REGION"

DLQ_URL="$(aws sqs get-queue-url \
  --queue-name "$(terraform -chdir=infra/app output -raw async_eventing_dlq_name)" \
  --query QueueUrl \
  --output text \
  --region "$AWS_REGION")"

aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names All \
  --region "$AWS_REGION"
```

Inspect app and consumer logs:

```bash
aws logs tail "/ecs/${STACK_NAME}/$(terraform -chdir=infra/app output -raw primary_edge_service_name)" \
  --since 30m \
  --region "$AWS_REGION"

aws logs tail "/ecs/${STACK_NAME}/event-consumer" \
  --since 30m \
  --region "$AWS_REGION"
```

## Log Checks

When Grafana or Loki is reachable, inspect app and consumer logs in the same
window:

```logql
{stack="<stack-name>", service="api"} |= "order_event_publish_failed"
```

```logql
{stack="<stack-name>", service="event-consumer"}
```

Keep the SQS DLQ CloudWatch alarm in the flow because Dapr delegates queue and
parking behavior to SNS/SQS in this stack.

## Common Causes

- The Dapr subscriber callback failed the same message five times.
- A deploy changed event payload handling without preserving idempotency.
- The event consumer task role lost SNS/SQS permissions required by Dapr.
- The Dapr component config points at the wrong topic, queue, or DLQ name.
- AWS SNS/SQS API calls from the private task cannot reach AWS through NAT or
  VPC endpoints.

## Recovery

If the consumer cannot relay or consume events, first restore queue access:

```bash
aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw primary_edge_service_name)" \
  --region "$AWS_REGION"

aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw event_consumer_service_name)" \
  --region "$AWS_REGION"
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
  --region "$AWS_REGION"
```

Only replay messages after the consumer defect is fixed. Preserve the original
`event_id` and `idempotency_key`; consumers must treat those as the duplicate
detection key.

## Success Criteria

- Consumer logs contain `outbox_relay` entries only when messages are published
  or fail, and `event_consumed` entries when messages are consumed.
- `outbox_messages` rows move from `pending` or `processing` to `published`.
- `event_receipts` records the consumed `event_id`.
- The DLQ has zero visible messages.
- The CloudWatch alarm returns to `OK`.

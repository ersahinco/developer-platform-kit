# Dapr Portability Contract

Dapr is the application-facing eventing boundary for this repo. Application
code should know Dapr pub/sub names, topics, CloudEvents, sidecar endpoints, and
outbox semantics. It should not know whether the current runtime implements
that component with SNS/SQS, Redis, Kafka, Azure Service Bus, GCP Pub/Sub, or
another broker.

## Application Contract

| Area | Contract |
| --- | --- |
| Publish API | Application infrastructure adapters publish through the Dapr HTTP sidecar. |
| Subscribe API | Runtime services expose Dapr subscription metadata and handlers, not provider queue handlers. |
| Event shape | Events preserve stable names, IDs, CloudEvent metadata, and payload fields. |
| Durability | The application outbox remains the durable handoff from database commit to event relay. |
| Idempotency | Consumers record receipts or equivalent idempotency state before treating delivery as complete. |
| Resiliency | Dapr retry/circuit-breaker settings are bounded and component-scoped. |
| Observability | Relay and consume outcomes emit structured logs, Prometheus metrics when hosted, and release/incident evidence. |

## Current AWS Implementation

The current runtime implements the `order-events-pubsub` Dapr component with
AWS SNS/SQS FIFO resources. Terraform owns the topic, queue, DLQ, encryption,
permissions, runtime component manifests, and SQS DLQ alarm. Those details stay
in `infra/`, `dapr/`, runbooks, and delivery scripts.

Provider-native SQS metrics are acceptable for the AWS platform edge. They must
not replace the app-facing Dapr/outbox contract or make app code import AWS
broker APIs.

## Future Runtime Requirements

Before changing the broker implementation or adding a runtime:

- Keep `ORDER_EVENTS_PUBSUB_NAME`, topic names, event names, and CloudEvent
  semantics stable unless every runtime should change.
- Keep provider component manifests outside domain/application code.
- Map the Dapr component to the runtime broker that fits the operating need.
- Keep retry, dead-letter, and idempotency behavior documented.
- Preserve incident evidence query hints for relay success, consume success,
  failures, and parked messages.
- Add contract tests before calling the new component supported.

Do not broaden Dapr into secrets, config, workflow, state, or service invocation
until a concrete workload needs that capability.

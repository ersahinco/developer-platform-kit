# Platform Capabilities

This document is the current capability map for the platform monorepo seed.

Use it to answer:

- what capabilities the platform currently standardizes
- which layer owns each capability
- where to extend the repo when a new workload needs more

The goal is clarity, not a new abstraction model.

## Current Capabilities

| Capability | Workload-facing contract | Current owner |
|---|---|---|
| HTTP service edge | `/health`, `/ready`, `/metrics`, structured logs, immutable image rollout | `apps/api`, `platform/workloads.json`, `infra/app/edge.tf`, workflows |
| Internal async service | long-running internal service shape, direct DB access, Dapr-backed event handling | `apps/order_event_consumer`, `platform/workloads.json`, `infra/app/workload_jobs.tf`, `infra/app/messaging.tf` |
| Dapr pub/sub | app id, pub/sub name, topic, resiliency semantics | `platform/concerns/dapr/`, `platform/workloads.json`, `packages/infrastructure/dapr` |
| Operator job execution | one-off job shape, idempotent rerun expectation, structured completion events | `apps/backfill_worker`, workflows, `infra/app/workload_jobs.tf` |
| Scheduled job execution | recurring job shape, scheduler-driven run pattern, export success expectations | `apps/data_export_job`, `infra/app/workload_jobs.tf`, `infra/app/object_storage.tf` |
| Database rollout safety | runtime read/write mode switches, backfill, contract migration flow | `db/`, `apps/api`, `packages/application`, runbooks |
| Local observability | Prometheus, Loki, Tempo, Grafana, Promtail | `platform/concerns/observability/`, `compose.yaml` |
| Cloud observability signals | CloudWatch logs, CloudWatch alarms, optional ADOT sidecar | `infra/app`, `scripts/observability/`, runbooks |
| Release evidence | portable release event, artifact upload, optional Loki push | workflows, `scripts/observability/release_event.py` |
| Incident evidence | portable bundle with ECS, alarms, release context, query hints | `scripts/observability/incident_evidence_bundle.py` |
| Runtime conformance | external proof that workloads satisfy the declared contract | `platform/runtime-conformance.json`, `tests/runtime/`, `make runtime-conformance` |

## Ownership Rules

- Add workload need to `platform/workloads.json`
- Add shared runtime concern to `platform/concerns/`
- Add provider/runtime implementation to `infra/`, workflows, or scripts
- Add reusable workflow or adapter logic only after repetition is proven

## Not Yet Platform Capabilities

These are intentionally not standardized yet:

- Dapr state store, bindings, workflows, actors, or secrets
- analytics orchestration or data transformation stacks
- hosted Grafana/Loki/Tempo/Prometheus runtime modules
- a second cloud/runtime target
- generic provider-neutral infrastructure modules

Add them only when a real workload or operating need appears.

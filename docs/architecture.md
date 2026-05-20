# Architecture

Repo shape and placement rules.

`aws-sdlc-containers` is a platform monorepo seed first and an AWS/ECS runtime
second. Portable value lives in the contract around OCI images, explicit
workload hosts, inward package boundaries, Terraform-owned runtime resources,
delivery gates, and portable observability and evidence.

Use companion docs for detail:

- [Platform Contract](platform-contract.md): workload expectations and metadata ownership
- [Platform Capabilities](platform-capabilities.md): implemented capability surface
- [Data](data.md): schema rollout and export behavior
- [Deployment](deployment.md): AWS rollout sequence
- [Observability](observability.md): telemetry and evidence behavior

## Model

Three layers:

- `infra/catalog/`: reusable cloud building blocks
- `platform/concerns/`: shared runtime capabilities
- `apps/`: reference consumers of the platform contract

Current assembly roots stay explicit:

- `infra/platform`
- `infra/app`
- `platform/workloads.json`

## Target Shape

- `apps/`: workload hosts
- `packages/`: reusable behavior and adapters
- `platform/`: shared contract and concern definitions
- `infra/`: runtime-specific implementation and catalog
- `scripts/`: explicit edge automation, never hidden orchestration

## Current Defaults

- One repo, one platform monorepo seed, one shared database reference
- Multiple reference workloads under `apps/`
- Explicit operational classes: edge service, internal service, operator job, scheduled job
- Split Terraform ownership: `infra/platform` for bootstrap, `infra/app` for runtime resources
- One public API edge protected by WAF
- One PostgreSQL database with Liquibase-managed history
- One scheduled export path and one async order-event path

These are runtime defaults, not portable guarantees. Keep portable behavior in
the contract and runtime mechanics at the platform edge.

## Package Map

- `packages/domain`: pure entities, value objects, domain events
- `packages/application`: use cases, ports, workflow logic
- `packages/infrastructure`: SQLAlchemy, Dapr, storage, runtime adapters
- `apps/*`: settings, routes, lifecycle, wiring

Similar names across layers are expected:

- `packages/application/data_export.py`: export use case
- `packages/infrastructure/data_export.py`: SQL/file/S3 adapters
- `apps/data_export_job/`: runnable host

Dependencies point inward:

```text
apps/*  -> packages/application -> packages/domain
apps/*  -> packages/infrastructure
packages/infrastructure -> packages/application + packages/domain
```

Operational classes point outward:

- `api`: public edge service
- `order_event_consumer`: internal async service
- `backfill_worker`: operator-triggered job
- `data_export_job`: scheduler-triggered job

Portable meaning lives in
[Platform Contract](platform-contract.md#operational-class).

## Ownership

| Path | Owns |
|---|---|
| `.github/workflows/` | CI, security, app build/deploy, infra plan/apply |
| `apps/` | workload entrypoints and runtime wiring |
| `packages/domain` | pure domain behavior |
| `packages/application` | use cases and stable ports |
| `packages/infrastructure` | SQL, Dapr, storage, runtime adapters |
| `db/` | Liquibase, bootstrap SQL, PgBouncer assets |
| `infra/catalog` | reusable AWS infrastructure building blocks |
| `infra/platform` | shared platform and bootstrap resources |
| `infra/app` | runtime resources |
| `platform/concerns/` | Dapr, observability, security, policy, networking |
| `platform/workloads.json` | temporary application specification |
| `platform/runtime-conformance.json` | local/CI runtime fixture data |
| `scripts/` | CI, operator, release, observability, data helpers |
| `tests/` | API, application, runtime, infra, contract checks |

Rules:

- Keep `apps/*` thin.
- Keep domain and application free of provider SDKs and runtime framework code.
- Add new folders only when there is real behavior and a clear owner.

## Platform Principles

- Use standard tools directly.
- Prefer metadata plus tests over wrappers.
- Keep delivery ownership split where review matters.
- Add shared abstractions only after repeated need is proven.
- Every supported workload must be operable, observable, and testable by default.

## Database Capability Ownership

| Capability | Tables | Primary writers |
|---|---|---|
| Order write model | `customers`, `orders`, `order_contact_email` | API and backfill worker |
| Runtime configuration | `app_runtime_config` | API admin endpoints and Liquibase seed data |
| Outbox and receipts | `outbox_messages`, `order_event_receipts`, `idempotency_keys` | API and order event runtime |
| Migration and backfill control | `backfill_progress`, `DATABASECHANGELOG`, `DATABASECHANGELOGLOCK` | Liquibase and backfill worker |
| Export outputs | S3 data hub objects | data export job |

Detailed rollout and eventing rules live in [Data](data.md) and
[Platform Contract](platform-contract.md#eventing).

## Runtime Split

- `infra/platform`: bootstrap, network, GitHub OIDC
- `infra/app`: RDS, ECS, ALB edge, jobs, messaging, observability wiring

This keeps lifecycle boundaries explicit without turning the repo into an
environment-promotion demo.

## Deferred On Purpose

- Backfill throttling from live database pressure
- Mixed-version rolling-deploy coordination during dual-write windows
- PgBouncer exhaustion mitigation beyond current pool sizing
- Snapshot/restore automation before destructive contract migrations
- Broader Dapr capabilities beyond pub/sub
- A second runtime target without a real operating reason

When one becomes real, decide whether it changes the portable contract, the
current capability inventory, or only the AWS runtime implementation, then edit
the owning doc for that layer.

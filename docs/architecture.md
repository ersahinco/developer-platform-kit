# Architecture

`aws-sdlc-containers` is a platform monorepo seed first and an AWS/ECS
implementation second. The current runtime stays intentionally narrow: one AWS
account and region, one ECS cluster, one PostgreSQL database, and one set of
reference workloads that prove safe in-place rollout.

The reusable architecture is the contract around proven tools: OCI images,
explicit workload hosts, inward-facing domain and application packages, runtime
adapters at infrastructure edges, Terraform-owned runtime resources, GitHub
Actions delivery gates, platform concerns, and portable observability and
evidence.

## Repository Model

The repository is evolving toward three explicit layers:

- Infrastructure catalog: reusable cloud building blocks under `infra/catalog`
- Platform concerns: shared runtime capabilities under `platform/concerns`
- Workload examples: reference consumers of the platform contract under `apps/`

Until that evolution is complete, `infra/platform` and `infra/app` remain the
deployable assembly roots, and `platform/workloads.json` remains the temporary
application specification.

## Current Architecture Contract

- One repository, one platform monorepo seed, one shared database reference
- Multiple reference workload hosts under `apps/`
- Explicit workload operational classes: edge service, internal service,
  operator job, scheduled job
- Split Terraform ownership: `infra/platform` for bootstrap and shared platform
  concerns, `infra/app` for runtime resources
- One public API edge protected by WAF
- One PostgreSQL database with Liquibase-managed schema history
- One scheduled export workload and one async order-event path

## Package Map

- `packages/domain`: pure entities, value objects, and domain events
- `packages/application`: use cases, ports, and workflow logic
- `packages/infrastructure`: SQLAlchemy, Dapr, storage, and runtime adapters
- `apps/*`: reference workload hosts with settings, routes, lifecycle, and wiring

This means similarly named files can legitimately exist in both places when
they represent different layers. For example:

- `packages/application/data_export.py` owns the export use case
- `packages/infrastructure/data_export.py` owns SQL/file/S3 adapters
- `apps/data_export_job/` owns the runnable workload host

See [apps/README.md](../apps/README.md) and [packages/README.md](../packages/README.md)
for the short contributor-facing version of this rule.

Dependencies point inward:

```text
apps/*  -> packages/application -> packages/domain
apps/*  -> packages/infrastructure
packages/infrastructure -> packages/application + packages/domain
```

Operational class points outward:

- `api` is the public edge service
- `order_event_consumer` is the internal async service
- `backfill_worker` is the operator-triggered job
- `data_export_job` is the scheduler-triggered job

## Repo Ownership

Use these boundaries when deciding where a change belongs:

| Path | Owns |
|---|---|
| `.github/workflows/` | CI, security, app build/deploy, infra plan/apply |
| `apps/` | reference workload entrypoints and runtime wiring |
| `packages/domain` | pure domain behavior |
| `packages/application` | use cases and stable ports |
| `packages/infrastructure` | SQL, Dapr, storage, and runtime adapters |
| `db/` | Liquibase, bootstrap SQL, PgBouncer assets |
| `infra/catalog` | reusable AWS infrastructure building blocks as they are extracted |
| `infra/platform` | shared platform and bootstrap resources |
| `infra/app` | runtime resources |
| `platform/concerns/` | Dapr, observability, security, policy, and networking concerns |
| `platform/workloads.json` | temporary application specification |
| `platform/runtime-conformance.json` | local/CI runtime fixture data for external conformance checks |
| `scripts/` | CI, operator, release, observability, and data helpers |
| `tests/` | API, application, runtime, infra, and contract checks |

Keep `apps/*` thin, keep domain/application free of provider SDKs and runtime
framework code, and add new folders only when there is real behavior and a
clear owner.

## Database Capability Ownership

The project keeps one PostgreSQL database and documents ownership by capability,
not by fake service boundaries:

| Capability | Tables | Primary writers |
|---|---|---|
| Order write model | `customers`, `orders`, `order_contact_email` | API and backfill worker |
| Runtime configuration | `app_runtime_config` | API admin endpoints and Liquibase seed data |
| Outbox and receipts | `outbox_messages`, `order_event_receipts`, `idempotency_keys` | API and order event runtime |
| Migration and backfill control | `backfill_progress`, `DATABASECHANGELOG`, `DATABASECHANGELOGLOCK` | Liquibase and backfill worker |
| Export outputs | S3 data hub objects | data export job |

## Schema Migration Lifecycle

The reference migration moves `orders.billing_email` into
`order_contact_email` with the standard expand, dual-write, backfill, switch,
and contract pattern.

- `WRITE_MODE` controls where new writes go
- `READ_MODE` controls where reads come from
- Both values live in `app_runtime_config`
- The API exposes admin endpoints so rollout can advance or roll back without a
  redeploy

This is intentionally one of the main teaching paths in the repo because it
exercises rollout safety, one-off jobs, and rollback boundaries without adding
extra business complexity.

## Async Order Events

The async path is intentionally narrow but real:

- The API writes `order.created.v1` to the outbox in the same transaction as
  the order
- `order-event-consumer` relays outbox rows through the Dapr sidecar
- The current runtime maps Dapr pub/sub to AWS SNS/SQS
- Consumers record receipts and keep delivery idempotent

Dapr is the standard app-facing transport boundary here. Broker details stay in
`infra/`, `platform/concerns/dapr/`, and runtime scripts.

The platform monorepo direction keeps Dapr in scope because workload complexity
and portability needs are expected to grow. The repo should keep Dapr
declarative and platform-owned rather than wrapping it in a custom framework.

## Platform Choices

- PgBouncer sits between the app and PostgreSQL for the long-running service
  path
- Liquibase connects directly to PostgreSQL for DDL
- Local runtime uses Compose plus the OSS observability stack
- Cloud runtime uses ECS, RDS, ALB/WAF, CloudWatch alarms, and GitHub Actions

## Split-Root Strategy

The repo uses one long-lived AWS stack split into platform and app Terraform
roots.

- `infra/platform` owns bootstrap, network, and GitHub OIDC concerns
- `infra/app` owns runtime resources such as RDS, ECS, ALB edge, jobs,
  messaging, and observability wiring

This keeps lifecycle boundaries clear without turning the project into an
environment-promotion demo.

## What's Intentionally Omitted

These are deferred on purpose:

- Backfill throttling based on live database pressure
- Explicit rolling-deploy coordination across mixed app versions in the
  dual-write window
- PgBouncer exhaustion mitigation beyond current pool sizing
- Snapshot/restore automation before destructive contract migrations
- Broader Dapr capabilities beyond the current pub/sub boundary
- A second runtime target without a real operating reason

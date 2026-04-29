# Architecture Notes

The canonical detailed architecture remains in `../ARCHITECTURE.md` while the
repo is being reorganized. This page is the stable docs entrypoint for the
monorepo direction.

## Current Architecture

- A single ECS-oriented platform stack.
- One FastAPI app service.
- One PgBouncer sidecar in front of Postgres.
- One RDS PostgreSQL database.
- Liquibase-managed schema changes.
- A one-off backfill worker for migration support.
- GitHub Actions for validation, image build, migration, deploy, and worker run.

The current workload proves safe rollout through additive schema changes,
runtime read/write switches, and one-off ECS tasks.

## Target Architecture

The target is a modular monolith monorepo:

- `apps/` contains deployable runtime entrypoints such as API, workers, jobs, and admin tasks.
- `packages/core/` contains pure domain and application logic.
- `packages/adapters/` contains implementations for Postgres, queues, object storage, external APIs, and observability.
- `db/` continues to own database migrations and local database assets.
- `infra/` continues to own AWS infrastructure.
- `ops/`, `security/`, and `docs/` grow only when there is real content to put there.

The application remains one product. Multiple ECS workloads are runtime shapes,
not separate business systems.

## Dependency Direction

The intended dependency direction is:

```text
apps/*
  -> packages/adapters
  -> packages/core/application
  -> packages/core/domain
```

Domain code must not import FastAPI, SQLAlchemy, boto3, HTTP clients, or queue
libraries. Adapters implement ports defined by the core package. App entrypoints
wire the concrete dependencies together.

## Current Boundary

The API now wires HTTP handlers from `apps/api/` to local workspace packages:

- `packages/core/` owns pure entities and repository/config ports.
- `packages/adapters/` owns SQLAlchemy models and Postgres repository implementations.
- `apps/api/` owns FastAPI schemas, routes, runtime settings, and session lifecycle.

Future restructuring should preserve that direction: apps depend inward on
packages, adapters implement core ports, and core stays framework-free.

## More Detail

- Existing design rationale: `../ARCHITECTURE.md`
- Target inspiration: `../.idea/architecture.md`
- Shared roadmap: `ROADMAP.md`

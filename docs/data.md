# Data

This is the canonical data contract for the current reference workload:

- zero-downtime schema rollout with Liquibase, dual write, backfill, read cutover,
  and contract
- PostgreSQL portability as the workload database contract
- stable object-storage paths and manifests for the export job

For request correlation across logs, traces, tables, and exports, use
[Observability](observability.md).

## Current Flow

Application path:

```text
API request
  -> FastAPI route
  -> application use case
  -> repository port
  -> SQLAlchemy repository
  -> PgBouncer
  -> Postgres
```

Support paths:

```text
Liquibase task -> Postgres direct connection
Backfill worker -> Postgres direct connection -> checkpointed copy
Data export job -> Postgres direct connection -> raw CSV -> manifest -> optional S3 upload
```

Liquibase and jobs connect directly because DDL and batch work need stable
session behavior. The API uses PgBouncer transaction pooling for runtime
traffic.

## Database Contract

The application contract is PostgreSQL semantics, not Amazon RDS itself. A
future runtime may use another managed PostgreSQL implementation if the app and
jobs do not need code changes.

| Area | Contract |
|---|---|
| Engine | PostgreSQL-compatible SQL, transactions, constraints, indexes, and Liquibase locking |
| Connection input | Services accept `DATABASE_URL`; jobs accept their own database URL |
| Alternate input | Runtimes may compose `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, and `DB_PASSWORD` |
| Pooling | request-serving services use PgBouncer; Liquibase and jobs connect directly |
| Migrations | Liquibase owns DDL and migration history |
| Readiness | long-running workloads expose database readiness through `/ready` |
| Rollback | additive before contract; after destructive contract changes, recover by restore or forward fix |

Database implementation details stay in `packages/infrastructure/db`, `db/`,
runtime settings, and delivery edges. Domain and application code stay free of
SQLAlchemy, drivers, and provider APIs.

Do not add a second database provider only to prove portability.

## Export Contract

`apps/data_export_job` exports `order_contact_email` first to a local path that
matches the object-store shape, then publishes a manifest only after the raw
CSV succeeds and validates.

Run it locally:

```bash
make data-export
```

The stable object layout is:

- `raw/order_contact_email/dt=<date>/<run-id>.csv`
- `manifests/order_contact_email/dt=<date>/<run-id>.json`

The contract is:

| Area | Contract |
|---|---|
| Dataset path | stable dataset name and partitioned path |
| Run identity | logical run id for traceability and idempotency |
| Write ordering | raw object before manifest |
| Integrity | manifest byte count and SHA-256 match the raw object |
| Adapter boundary | provider SDKs stay in infrastructure code and runtime scripts |
| Evidence | job success and failure remain visible in logs and release or incident evidence |

Do not add another object store only to prove portability.

## AWS Runtime

AWS currently provides:

- one private data hub bucket named `<stack-name>-data-hub-<account-id>`
- versioning, encryption, blocked public access, and short noncurrent cleanup
- one scheduled ECS export task using the latest active task definition family

The bucket preserves the same prefixes used locally:

```text
s3://<bucket>/
|-- raw/<dataset>/dt=<YYYY-MM-DD>/
|-- curated/<dataset>/dt=<YYYY-MM-DD>/
`-- manifests/<dataset>/dt=<YYYY-MM-DD>/<run-id>.json
```

There are no placeholder objects. The scheduled task creates objects only when
it runs.

## Deferred

These are intentionally out of scope until a real workload needs them:

- streaming ingestion
- cross-account sharing
- Glue or Athena layers
- Lake Formation permissions
- data quality frameworks
- multi-step orchestration

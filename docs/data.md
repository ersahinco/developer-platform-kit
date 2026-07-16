# Data

Canonical data contract for contract-governed workloads:

- zero-downtime schema rollout with Liquibase, dual write, backfill, cutover, contract
- PostgreSQL portability as the workload database contract
- stable object-storage paths and manifests for the export job

See [Platform Contract](platform-contract.md),
[Architecture](architecture.md), and [Observability](observability.md).

## Flow

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
Booking API -> PgBouncer -> Postgres unique slot constraint -> reserved or conflict
Lake orders job -> CSV batches -> raw Parquet -> deduplicated projection -> manifest
Churn training job -> fixture -> versioned model + lineage/promotion manifest
Churn prediction API -> compatible promoted model -> prediction + model identity
```

Liquibase and jobs connect directly because DDL and batch work need stable
sessions. The API uses PgBouncer transaction pooling.

## Database Contract

The contract is PostgreSQL semantics, not Amazon RDS.

| Area | Contract |
|---|---|
| Engine | PostgreSQL-compatible SQL, transactions, constraints, indexes, Liquibase |
| Connection input | workloads accept `DATABASE_URL`; runtimes choose pooled or direct values |
| Alternate input | runtimes may compose `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, `DB_PASSWORD` |
| Pooling | request-serving services use PgBouncer; Liquibase and jobs connect directly |
| Migrations | Liquibase owns DDL and migration history |
| Readiness | long-running workloads expose database readiness through `/ready` |
| Rollback | additive before contract; after destructive changes, recover by restore or forward fix |

Database implementation details stay in `packages/infrastructure/db`, `db/`,
runtime settings, and delivery edges. Domain and application code stay free of
drivers, SQLAlchemy, and provider APIs.

Do not add a second database provider only to prove portability.

## Export Contract

`apps/data_export_job` exports `order_contact_email` to a local path matching
the object-store shape, then publishes a manifest only after the raw CSV
succeeds.

```bash
make data-export
```

Stable layout:

- `raw/order_contact_email/dt=<date>/<run-id>.csv`
- `manifests/order_contact_email/dt=<date>/<run-id>.json`

| Area | Contract |
|---|---|
| Dataset path | stable dataset name and partitioned path |
| Run identity | logical run id for traceability and idempotency |
| Write ordering | raw object before manifest |
| Integrity | manifest byte count and SHA-256 match the raw object |
| Adapter boundary | provider SDKs stay in infrastructure code and runtime scripts |
| Evidence | job success and failure stay visible in logs and release or incident evidence |

Do not add another object store only to prove portability.

## Enterprise Pattern Proofs

The local-only experimental workloads exercise failure modes that matter at
enterprise scale without claiming production admission:

- `booking_api` is reached through Dapr service invocation while the
  double-booking invariant stays in PostgreSQL as a unique
  `(resource_id, starts_at)` constraint. The concurrency test uses independent
  sessions and proves exactly one committed reservation.
- `lake_orders_ingest_job` rebuilds a projection from source batches, selects
  the latest update per order, flags records older than the ingest watermark,
  and publishes a manifest only after raw and curated artifacts succeed.
- `churn_model_train_job` produces a deterministic model identity, input hash,
  bounded evaluation, drift summary, and promotion decision.
- `churn_prediction_api` loads only schema-compatible promoted artifacts and
  includes model version, run id, and training-data hash in prediction events.

These are intentionally small pattern proofs, not generic analytics or MLOps
platforms. Run them with:

```bash
make enterprise-pattern-proofs
```

## AWS Runtime

- one private data hub bucket named `<stack-name>-data-hub-<account-id>`
- versioning, encryption, blocked public access, short noncurrent cleanup
- one scheduled ECS export task using the latest active task definition family

The bucket preserves local prefixes:

```text
s3://<bucket>/
|-- raw/<dataset>/dt=<YYYY-MM-DD>/
|-- curated/<dataset>/dt=<YYYY-MM-DD>/
`-- manifests/<dataset>/dt=<YYYY-MM-DD>/<run-id>.json
```

No placeholder objects. The task creates objects only when it runs.

## Deferred

- streaming ingestion
- cross-account sharing
- Glue or Athena layers
- Lake Formation permissions
- generic data quality frameworks
- multi-step orchestration

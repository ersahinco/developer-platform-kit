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
Lake orders ingest job -> checked-in order batches -> Parquet -> DuckDB/dbt transform -> manifest
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

## Lake Orders Ingest Workload

`apps/lake_orders_ingest_job` is a local-first operator job that proves data
engineering behavior without adding a data platform contract. It reads checked-in
order batches, writes raw and curated Parquet, runs the checked-in dbt model
through DuckDB, and emits structured run evidence.

Stable layout:

- `raw/lake_orders/dt=<date>/<run-id>.parquet`
- `curated/lake_orders/dt=<date>/<run-id>.parquet`
- `manifests/lake_orders/dt=<date>/<run-id>.json`

Evidence includes `run_id`, `row_count`, `late_arrival_count`,
`parquet_object_count`, `transform_tool`, `transform_execution`, and artifact
paths. `transform_tool` remains workload evidence; it is not a platform
metadata field. The current Python 3.14 runtime may use
`duckdb_sql_fallback` when the dbt CLI cannot start, while still executing the
workload-local dbt model SQL and model checks.

DuckLake is deferred. It is a reasonable future experiment for this workload,
but it should remain a workload implementation detail unless a real runtime
target need appears.

## Churn Model Workloads

`apps/churn_model_train_job` and `apps/churn_prediction_api` prove the model
training plus inference shape as concrete workloads. The training job reads a
checked-in fixture dataset, writes a model artifact and manifest, and emits
evidence with `run_id`, `model_version`, training row count, metrics, and drift
summary. The prediction API loads a model artifact and exposes `/health`,
`/ready`, `/metrics`, and `/predict`.

Stable training layout:

- `models/churn_prediction/dt=<date>/<run-id>.json`
- `manifests/churn_prediction/dt=<date>/<run-id>.json`

Model metrics and drift summaries are workload evidence. They do not add MLOps
fields to the workload contract. The runtime edge still decides where logs and
Prometheus-compatible metrics go.

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
- data quality frameworks
- multi-step orchestration

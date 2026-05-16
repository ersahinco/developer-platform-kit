# Data

This is the canonical data and storage document. It covers the current
zero-downtime schema migration, PostgreSQL portability contract, and data export
object contract in one place.

For a compact operator map across AWS edge, ECS tasks, Postgres tables, S3
objects, logs, metrics, and downstream order events, use
[Observability](observability.md#operator-debug-map).

## Current Flow

The current data reliability example is the zero-downtime schema migration:
Liquibase expands the schema, the app dual-writes, the worker backfills, reads
switch to the new table, and contract removes the old column only after the new
path is verified.

```text
API request
  -> FastAPI route
  -> application use case
  -> repository port
  -> SQLAlchemy repository
  -> PgBouncer
  -> Postgres
```

Migration support flow:

```text
Liquibase task
  -> Postgres direct connection

Backfill worker task
  -> Postgres direct connection
  -> checkpointed batch copy
  -> idempotent insert into expanded table

Data export job
  -> Postgres direct connection
  -> raw/order_contact_email/dt=<date>/<run-id>.csv
  -> manifests/order_contact_email/dt=<date>/<run-id>.json
  -> optional S3 upload to the same relative keys
```

Liquibase bypasses PgBouncer because DDL requires a stable session connection.
The app uses PgBouncer because runtime traffic benefits from transaction-mode
pooling.

## Database Contract

This project depends on PostgreSQL semantics, not on RDS as an application
contract. RDS is the current AWS runtime implementation. A future runtime could
use Supabase, Neon, Cloud SQL for PostgreSQL, Azure Database for PostgreSQL, or
another managed PostgreSQL service if it satisfies this contract without app
code changes.

| Area | Contract |
| --- | --- |
| Engine | PostgreSQL-compatible SQL, transactions, constraints, indexes, and advisory migration locking used by Liquibase. |
| Connection strings | Services accept `DATABASE_URL`; jobs accept their job-specific URL such as `BACKFILL_DATABASE_URL` or `DATA_EXPORT_DATABASE_URL`. |
| Composed config | Runtimes may provide `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, and injected `DB_PASSWORD` instead of a full URL. |
| Secrets | `DB_PASSWORD` is injected by the runtime secret mechanism and is not committed, logged, stored in images, or stored in plaintext Terraform variables. |
| Pooling | Request-serving services use PgBouncer transaction pooling. Long-running jobs and Liquibase connect directly to PostgreSQL. |
| Migrations | Liquibase owns DDL, migration history, and migration locks. App containers do not apply schema changes at startup. |
| Readiness | `/ready` checks database availability for long-running workloads and reports `database` as a structured readiness check. |
| Rollback | Schema rollback stays forward-compatible until contract. After destructive contract changes, recovery is database restore or forward fix, not app image rollback. |

`packages/domain` and `packages/application` must not import SQLAlchemy,
PostgreSQL drivers, provider SDKs, or provider-specific database APIs. Database
implementation details belong in `packages/infrastructure/db`, `db/`, runtime
app settings, and platform/delivery edges.

CloudWatch is acceptable for RDS CPU, storage, and connection pressure because
those are provider-managed infrastructure signals. CloudWatch must not become
the application observability contract. App-level database symptoms still show
up through readiness, Prometheus metrics, Loki logs, Tempo traces when enabled,
and release evidence.

Before replacing or adding a database provider, prove PostgreSQL compatibility,
Liquibase execution, pooling strategy, direct job connections, runtime secret
injection, backup/restore or point-in-time recovery, provider-native metrics at
the platform edge, explicit Terraform ownership, workload database metadata in
`platform/workloads.json`, and runtime conformance from outside the container.

Do not add a second database provider only to prove portability. Add one when a
real workload benefits from a different managed PostgreSQL implementation.

## Data Export Job

`apps/data_export_job` is the first deliberately small data-hub-shaped job. It
exports `order_contact_email` to local filesystem paths that mirror the S3
convention, then writes a manifest only after the CSV succeeds and the manifest
has been validated against the raw file.

Run it locally through Docker Compose:

```bash
make data-export
```

The job writes into the `data_exports` Docker volume by default. For tests and
ad hoc local runs, set `DATA_EXPORT_OUTPUT_DIR` to a temporary directory and
`DATA_EXPORT_RUN_ID` to make the output path deterministic.

Set `DATA_EXPORT_S3_BUCKET` to enable S3 mode. The job still writes the raw CSV
and manifest locally first, validates the manifest's raw byte count and SHA-256
checksum, then uploads the raw object before the manifest. If the raw upload
fails, the process exits non-zero before uploading a manifest.

The object convention is stable:
`raw/order_contact_email/dt=<date>/<run-id>.csv` and
`manifests/order_contact_email/dt=<date>/<run-id>.json`. Changing those paths
requires updating the data export tests and manifest contract in the same slice.

## Object Storage Contract

S3 is the current AWS implementation for app-owned object storage. The portable
contract is the data product shape: dataset paths, manifest fields, idempotent
run IDs, write ordering, and provider SDKs kept behind infrastructure adapters.

| Area | Contract |
| --- | --- |
| Datasets | Stable dataset names and partitioned paths. |
| Prefixes | `raw/`, `curated/`, and `manifests/` remain the durable object layout. |
| Run identity | A logical run ID makes exports idempotent and traceable. |
| Write ordering | Raw data is written and validated before the manifest is published. |
| Integrity | Manifest byte count and SHA-256 checksum match the raw object. |
| Evidence | Success and failure are visible through structured job logs and release or incident evidence. |
| Adapters | Provider SDK usage stays in `packages/infrastructure` or runtime scripts, not domain/application code. |

A future runtime may map the same contract to GCS, Azure Blob, Supabase Storage,
or another object store if it preserves the same relative object paths, manifest
fields, raw-before-manifest ordering, idempotent run IDs, runtime secret
injection, provider SDK isolation, and operator path documentation.

Do not add another object store only to prove portability.

## AWS Data Hub Bucket

Terraform creates one private S3 bucket named
`<stack-name>-data-hub-<account-id>` with versioning, server-side encryption,
public access blocking, bucket-owner-enforced object ownership, and a short
noncurrent-version cleanup rule.

The bucket reserves the same prefixes as the local export job:

```text
s3://<bucket>/
|-- raw/<dataset>/dt=<YYYY-MM-DD>/
|-- curated/<dataset>/dt=<YYYY-MM-DD>/
`-- manifests/<dataset>/dt=<YYYY-MM-DD>/<run-id>.json
```

There are no placeholder objects for these prefixes. S3 prefixes are virtual;
the scheduled export creates objects only when it runs.

## Scheduled ECS Export

Terraform defines one scheduled Fargate task named
`<stack-name>-data-export-job`. EventBridge Scheduler runs it daily by default
with `rate(1 day)`. The task connects directly to RDS, writes the local staging
files under `/tmp/aws-sdlc-containers-data-hub`, and uploads `raw/` and
`manifests/` objects to the data hub bucket.

The scheduler targets the task definition family rather than a fixed revision.
CI registers a fresh SHA-tagged task definition revision during manual deploys,
and the next scheduled run picks up that latest active revision.

## Deferred

- Streaming ingestion.
- Cross-account data sharing.
- Glue catalog and crawlers.
- Athena query layer.
- Lake Formation permissions.
- Data quality frameworks.
- Multi-step orchestration.

Add these only when the toolkit has a real need for them.

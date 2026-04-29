# Data Flow Plan

The current data reliability example is the zero-downtime schema migration:
Liquibase expands the schema, the app dual-writes, the worker backfills, reads
switch to the new table, and contract removes the old column only after the new
path is verified.

Keep this as the primary data-flow teaching artifact until the rest of the
DevOps platform is stable.

## Current Flow

```text
API request
  -> FastAPI route
  -> domain port
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
```

Liquibase bypasses PgBouncer because DDL requires a stable session connection.
The app uses PgBouncer because runtime traffic benefits from transaction-mode
pooling.

## Local Export Job

`apps/data-export-job` is the first deliberately small data-hub-shaped job. It
exports `order_contact_email` to local filesystem paths that mirror the future
S3 convention, then writes a manifest only after the CSV succeeds.

This job is local proof only for now. The GitHub Actions app workflow runs its
tests, but it does not build or deploy a data-job image to AWS until the ECS
scheduled task and EventBridge trigger are added in a later slice.

Run it locally through Docker Compose:

```bash
make data-export
```

The job writes into the `data_exports` Docker volume by default. For tests and
ad hoc local runs, set `DATA_EXPORT_OUTPUT_DIR` to a temporary directory and
`DATA_EXPORT_RUN_ID` to make the output path deterministic.

## AWS Data Hub Bucket

Terraform now creates one private S3 bucket named
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
the export job creates the first objects when the ECS data job is wired in.

## Data Hub v1 Design

The first data hub should be deliberately small:

- One S3 bucket managed by Terraform. (Done.)
- Prefixes for `raw/`, `curated/`, and `manifests/`.
- Promote the existing local export job to an ECS data job.
- One EventBridge schedule that runs the job.
- One manifest file per export with row count, source query name, export time, and object keys.
- No Glue catalog, Athena, Kafka, Lake Formation, or multi-account sharing in v1.

## Acceptance Criteria for v1

- The job can run locally against the Compose database.
- The same container can run as an ECS one-off or scheduled task.
- Exports are idempotent for the same logical run ID.
- The manifest is written only after data export succeeds.
- Failure leaves either no manifest or a manifest marked as failed.
- IAM grants the job access only to the target bucket/prefix and required database secret.

## Deferred

- Streaming ingestion.
- Cross-account data sharing.
- Glue catalog and crawlers.
- Athena query layer.
- Lake Formation permissions.
- Data quality frameworks.
- Multi-step orchestration.

Add these only when the template has a real need for them.

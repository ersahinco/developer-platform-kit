# Data Flow Plan

The current data reliability example is the zero-downtime schema migration:
Liquibase expands the schema, the app dual-writes, the worker backfills, reads
switch to the new table, and contract removes the old column only after the new
path is verified.

For a compact operator map of the same data path across AWS edge, ECS tasks,
Postgres tables, S3 objects, logs, metrics, and downstream order events, use
[Operator Observability Map](operator-observability-map.md).

Keep this as the primary data-flow teaching artifact until the rest of the
DevOps platform is stable.

## Current Flow

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

## Local Export Job

`apps/data_export_job` is the first deliberately small data-hub-shaped job. It
exports `order_contact_email` to local filesystem paths that mirror the S3
convention, then writes a manifest only after the CSV succeeds and the manifest
has been validated against the raw file.

The GitHub Actions App Build workflow validates the job, builds and scans its
image, pushes it to ECR, and App Deploy registers the latest task definition
revision during manual deploys. The scheduled task owns recurring exports; the normal app
deploy does not run an export immediately.

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

V2 keeps the object convention stable:
`raw/order_contact_email/dt=<date>/<run-id>.csv` and
`manifests/order_contact_email/dt=<date>/<run-id>.json`. Changing those paths
requires updating the data export tests and the manifest contract in the same
slice.

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

## Data Hub v1 Design

The first data hub should be deliberately small:

- One S3 bucket managed by Terraform. (Done.)
- Prefixes for `raw/`, `curated/`, and `manifests/`.
- Promote the existing local export job to an ECS data job. (Done.)
- One EventBridge schedule that runs the job. (Done.)
- One manifest file per export with row count, source query name, export time,
  raw object key, raw byte count, raw SHA-256 checksum, and manifest object key.
- No Glue catalog, Athena, Kafka, Lake Formation, or multi-account sharing in v1 or V2.

## Acceptance Criteria for v1

- The job can run locally against the Compose database.
- The same container can run as an ECS one-off or scheduled task.
- Exports are idempotent for the same logical run ID.
- The manifest is written only after data export succeeds.
- The manifest's raw byte count and SHA-256 checksum match the raw CSV before
  the manifest is uploaded or emitted as the success signal.
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

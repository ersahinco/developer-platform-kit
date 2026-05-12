# Data And Object Storage Portability

S3 is the current AWS implementation for app-owned object storage. The portable
contract is the data product shape: dataset paths, manifest fields, idempotent
run IDs, write ordering, and provider SDKs kept behind infrastructure adapters.

## Portable Data Contract

| Area | Contract |
| --- | --- |
| Datasets | Stable dataset names and partitioned paths. |
| Prefixes | `raw/`, `curated/`, and `manifests/` remain the durable object layout. |
| Run identity | A logical run ID makes exports idempotent and traceable. |
| Write ordering | Raw data is written and validated before the manifest is published. |
| Integrity | Manifest byte count and SHA-256 checksum match the raw object. |
| Evidence | Success and failure are visible through structured job logs and release or incident evidence. |
| Adapters | Provider SDK usage stays in `packages/infrastructure` or runtime scripts, not domain/application code. |

## Current AWS Implementation

The current data export job writes local staging files first, then optionally
uploads raw and manifest objects to an S3 data hub bucket. Terraform owns the
bucket, encryption, public access blocking, versioning, lifecycle policy, and
job IAM permissions.

`DATA_EXPORT_S3_BUCKET` is the AWS runtime edge switch. It does not change the
portable manifest contract or the local file contract.

## Future Provider Requirements

A future runtime may map the same contract to GCS, Azure Blob, Supabase Storage,
or another object store if it proves:

- The same relative object paths and manifest fields are preserved.
- Raw-before-manifest write ordering is preserved.
- Idempotent re-runs for the same run ID are safe.
- Credentials are injected by the runtime secret mechanism.
- Provider SDK imports stay out of `packages/domain`,
  `packages/application`, and app business logic.
- Operator runbooks explain how to locate raw objects and manifests.

Do not add another object store only to prove portability.

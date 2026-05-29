# First 30 Minutes

Fast path for a new developer validating the delivery toolkit shape.

## 1. Prove The Local Runtime

```bash
make platform-toolkit-validate-local
```

This starts the local runtime, applies migrations, checks API health/readiness
and metrics, publishes through Dapr, runs data jobs, and finishes with runtime
conformance.

For a faster daily confidence pass after the stack is already warm:

```bash
make platform-toolkit-smoke-local
```

## 2. Inspect The App Surface

```bash
make api-smoke
make dapr-smoke
```

Use `api-smoke` for `/health`, `/ready`, and `/metrics`. Use `dapr-smoke` to
publish a CloudEvent through the local Dapr sidecar and confirm the event
consumer records it.

## 3. Inspect Local Data Artifacts

```bash
make data-export
make open-dataset-pipeline
make data-artifacts-list
```

The data export job and open dataset pipeline write raw, manifest, and DuckDB
artifacts into the local `data_exports` Docker volume.

## 4. Walk The Schema Rollout Shape

```bash
make backfill-once
```

This runs one bounded local backfill batch. Use it with
[Local Development](local-development.md#migration-rollout-walkthrough) when
walking the expand, dual-write, backfill, switch, and contract path.

## 5. Check Safe Cloud Readiness

```bash
make platform-toolkit-validate-cloud
make infra-validate-local
make workflow-dry-run-validate
make workflow-dry-run-commands
```

These commands do not mutate AWS. They validate workflow shape, platform
policy, contract/script behavior, Terraform syntax without remote backends, and
the generated GitHub workflow dry-run dispatch commands.

Use the real cloud-changing workflows only after review, immutable image
selection, and the confirmation inputs described in
[Deployment](deployment.md).

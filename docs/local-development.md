# Local Development

Canonical local setup and day-to-day runbook.

Use [Architecture](architecture.md) for ownership rules and
[Platform Contract](platform-contract.md) for portable workload rules.
Local development is a first-class runtime target for this platform monorepo:
it should be fast, contract-faithful, and provider-light so engineers can
iterate before touching cloud infrastructure.

Reference workloads:

- `apps/api`
- `apps/backfill_worker`
- `apps/data_export_job`
- `apps/event_consumer`
- `apps/open_dataset_pipeline`

Local-only workloads still belong in `apps/` when they have a real contract,
local proof, and owner. Reserve `examples/` for teaching, demo, and
reference-only samples.

## Preferred Setup

Prefer the dev container. Native host setup is fine with Docker Desktop,
Python 3.14+, and `uv`.

Key entrypoints:

- `compose.yaml`
- `Makefile`
- `pyproject.toml`
- `uv.lock`
- `.devcontainer/`

## Standard Local Flow

```bash
make dev
make migrate
make seed
make local-up
curl --fail --show-error http://127.0.0.1:8000/health
```

Use stepwise Docker commands only when you intentionally want the API without
the full local profile.

## Platform Toolkit Validation

Use this when validating the repo as a local-first delivery toolkit, not just
as a running API:

```bash
make platform-toolkit-validate-local
```

Use this shorter target when the local stack is already warm and you want a
fast confidence pass:

```bash
make platform-toolkit-smoke-local
```

It runs the standard local startup path, verifies `/health`, `/ready`, and
`/metrics`, publishes a CloudEvent through the local Dapr sidecar and confirms
the event consumer recorded it, runs the data export job, runs the
`open_dataset_pipeline` workload, and finishes with `make runtime-conformance`.

The target prints section headers before each slice. Docker and pytest still
show their native output so failures stay close to the tool that produced them.
The API check uses `make api-smoke`, which retries briefly while the container
finishes startup.

Startup targets pass Compose's orphan cleanup flag so stale containers from an
older project shape do not obscure the current run. Use `make local-reset` only
when you also want to remove local volumes.

## Local Data Artifacts

The data export and open dataset workloads write to the `data_exports` Docker
volume. Use these helpers to inspect or reset the local artifact surface:

```bash
make data-export
make open-dataset-pipeline
make data-artifacts-list
make data-artifacts-shell
make data-artifacts-clean
```

## Migration Rollout Walkthrough

1. Start Postgres and PgBouncer.
2. Apply Liquibase migrations.
3. Seed local data.
4. Start the API.
5. Advance `WRITE_MODE` to `dual`.
6. Run the backfill worker.
7. Advance `READ_MODE` to `new`.
8. Run tests.
9. Advance `WRITE_MODE` to `new`.
10. Apply the contract migration when ready.

Commands:

```bash
curl --fail --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"mode":"dual"}' \
  http://127.0.0.1:8000/admin/write-mode

make backfill-once

curl --fail --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"mode":"new"}' \
  http://127.0.0.1:8000/admin/read-mode
```

## Quality Checks

```bash
uv sync --all-packages --group dev --group scripts --group test
make lint
uv run pytest tests/ -v
```

Tests read migration phase from `app_runtime_config` and skip phase-specific
assertions when needed.

## Optional Targets

```bash
make observability
make dapr-up
make data-export
make open-dataset-pipeline
```

## Common Targets

```bash
make help
make dev
make local-up
make local-down
make local-reset
make observability
make dapr-up
make migrate
make seed
make api-smoke
make backfill-once
make data-export
make data-artifacts-list
make open-dataset-pipeline
make test
make lint
make fmt
```

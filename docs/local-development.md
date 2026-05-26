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

Local-only examples:

- `apps/open_dataset_pipeline`

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
curl --fail --show-error http://localhost:8000/health
```

Use stepwise Docker commands only when you intentionally want the API without
the full local profile.

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
  http://localhost:8000/admin/write-mode

docker compose run --rm -e BACKFILL_MAX_BATCHES=1 worker

curl --fail --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"mode":"new"}' \
  http://localhost:8000/admin/read-mode
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
make open-dataset-example
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
make open-dataset-example
make test
make lint
make fmt
```

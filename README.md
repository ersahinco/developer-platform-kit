# aws-sdlc-containers

`aws-sdlc-containers` is a lean AWS delivery sandbox for practicing the
software development lifecycle around ECS: local development, CI/CD, immutable
container images, reproducible Terraform, database migration safety, and
workload operations.

The project is intentionally small today: one AWS stack, one ECS cluster, one
FastAPI app, one backfill worker, one scheduled data export job, PgBouncer,
Liquibase, one PostgreSQL database, and one S3 data hub bucket. It is being shaped
gradually into a modular monolith monorepo for app, infra, data, and DevOps
work.

## Start Here

| Need | Go to |
|---|---|
| Current roadmap | [docs/ROADMAP_V2.md](docs/ROADMAP_V2.md) |
| V1 roadmap history | [docs/ROADMAP.md](docs/ROADMAP.md) |
| Architecture direction | [docs/architecture.md](docs/architecture.md) |
| Local development runbook | [docs/local-development.md](docs/local-development.md) |
| AWS deployment/runbook | [docs/deployment.md](docs/deployment.md) |
| Terraform root guide | [infra/README.md](infra/README.md) |
| DevOps toolchain | [docs/devops-toolchain.md](docs/devops-toolchain.md) |
| Data flow plan | [docs/data-flow.md](docs/data-flow.md) |
| Observability plan | [docs/observability.md](docs/observability.md) |
| Architecture decisions | [docs/adr/](docs/adr/) |

Read [docs/ROADMAP_V2.md](docs/ROADMAP_V2.md) before making DevOps,
infrastructure, data-flow, observability, security, or operator workflow
changes. V1 history remains in [docs/ROADMAP.md](docs/ROADMAP.md).

## What This Demonstrates

| Concern | Mechanism | Key files |
|---|---|---|
| SDLC baseline | GitHub Actions, immutable ECR tags, reproducible Terraform state | `.github/workflows/`, `infra/`, `Makefile` |
| Safe schema rollout | Expand, dual-write, backfill, switch, contract | `db/changelog/`, `apps/backfill-worker/src/aws_sdlc_backfill_worker/main.py` |
| Data export flow | Local and scheduled ECS export job with raw output, manifest, and S3 data hub writes | `apps/data-export-job/src/aws_sdlc_data_export_job/main.py`, `infra/base_data_hub_s3.tf`, `infra/support_jobs.tf` |
| Runtime config | DB-backed `WRITE_MODE` and `READ_MODE` switches | `packages/adapters/src/aws_sdlc_adapters/db/repository.py` |
| Connection pooling | PgBouncer in transaction mode | `docker-compose.yml`, `db/pgbouncer/pgbouncer.ini` |
| ECS deployment | Rolling app deploy plus one-off Liquibase and worker tasks | `.github/workflows/app.yml`, `infra/support_jobs.tf` |
| Infrastructure delivery | Terraform validate, plan, and manual apply | `.github/workflows/infra.yml`, `infra/` |

## Reference Workload

The current workload is a zero-downtime schema evolution exercise: move
`orders.billing_email` into a dedicated `order_contact_email` table.

The migration follows this lifecycle:

1. Expand: Liquibase creates the new table while the old column remains.
2. Dual-write: the app writes to both old and new locations.
3. Backfill: the worker copies historical rows in checkpointed batches.
4. Switch: reads move to the new table.
5. Contract: the old column is dropped after the new path is verified.

This stays in the repo because it exercises app delivery, database change
management, background jobs, rollback-safe sequencing, and ECS one-off tasks
without adding unnecessary business complexity.

## Current Project Layout

```text
aws-sdlc-containers/
|-- apps/
|   |-- api/             # FastAPI workload
|   |-- backfill-worker/ # Backfill worker workload
|   `-- data-export-job/ # Data export job
|-- packages/
|   |-- core/            # Pure domain entities and ports
|   `-- adapters/        # SQLAlchemy/Postgres adapter implementations
|-- db/                  # Liquibase changelog and Postgres assets
|-- infra/               # Single-stack Terraform
|-- scripts/             # Local and CI helper scripts
|-- tests/               # Pytest integration tests
|-- docs/                # Roadmap, docs entrypoints, ADRs
|-- .github/workflows/   # App and infra workflows
|-- docker-compose.yml
`-- Makefile
```

Target direction is an evolutionary monorepo with `apps/`, `packages/`,
`infra/`, `db/`, `docker/`, and `docs/`. Future `ops/` and `security/`
directories should appear only when they have real owned content. See
[docs/ROADMAP_V2.md](docs/ROADMAP_V2.md) for the current phase checklist.

## Quick Local Path

Prerequisites:

- Docker Desktop
- Python 3.12+
- `uv`

Start local Postgres and PgBouncer:

```bash
make dev
```

Apply migrations and seed data:

```bash
make migrate
make seed
```

Start the app and smoke test it:

```bash
docker compose build app
docker compose up -d app
uv run python scripts/smoke_test.py
```

Run tests:

```bash
uv sync --all-packages --group dev --group test
uv run python scripts/secret_scan.py .
uv run python scripts/dependency_audit.py
uv run ruff check apps/ packages/ tests/ scripts/
uv run pyright
uv run pytest tests/ -v
```

For the full migration walkthrough, read
[docs/local-development.md](docs/local-development.md).

Optional local observability is available through Docker Compose:

```bash
make observability
```

See [docs/observability.md](docs/observability.md) for the Prometheus, Loki,
and Grafana setup.

## CI/CD Shape

GitHub Actions workflows keep security, app, and infrastructure concerns separate:

- `security.yml`: high-confidence secret scanning and Python dependency audit on pull requests and `main`.
- `codeql.yml`: GitHub-native Python SAST on pull requests and `main`.
- `infra.yml`: Terraform fmt, validate, tflint, checkov, PR plan, and manual apply.
- `app.yml`: local workload validation, image build, Trivy scan, ECR push, Liquibase task, ECS service deploy, worker task run, and data export task registration.

Cloud-changing jobs are manual through `workflow_dispatch` and require typed
confirmation. AWS authentication uses GitHub OIDC, not long-lived access keys.

## Later Phases

This repo stays lean on purpose. Current operator-quality work is tracked in
[docs/ROADMAP_V2.md](docs/ROADMAP_V2.md), V1 history remains in
[docs/ROADMAP.md](docs/ROADMAP.md), and intentionally deferred hardening remains
documented in
[docs/architecture.md#whats-intentionally-omitted](docs/architecture.md#whats-intentionally-omitted).

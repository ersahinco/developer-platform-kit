# aws-sdlc-containers

`aws-sdlc-containers` is a lean AWS delivery sandbox for practicing the
software development lifecycle around ECS: local development, CI/CD, immutable
container images, reproducible Terraform, database migration safety, and
workload operations.

The project is intentionally small today: one ECS cluster, one FastAPI app, one
backfill worker, one scheduled data export job, PgBouncer, Liquibase, one
PostgreSQL database, one app-owned S3 object storage bucket, and split
platform/app Terraform roots. It is being shaped gradually into a modular
monolith monorepo for app, infra, data, and DevOps work.

## Start Here

| Need | Go to |
|---|---|
| How to continue work cleanly | [docs/engineering-loop.md](docs/engineering-loop.md) |
| Roadmaps and continuation rules | [docs/roadmaps.md](docs/roadmaps.md) |
| Architecture direction | [docs/architecture.md](docs/architecture.md) |
| Local development runbook | [docs/local-development.md](docs/local-development.md) |
| AWS deployment/runbook | [docs/deployment.md](docs/deployment.md) |
| Incident runbooks and drills | [docs/runbooks/README.md](docs/runbooks/README.md) and [docs/drills/README.md](docs/drills/README.md) |
| Terraform root guide | [infra/README.md](infra/README.md) |
| DevOps toolchain | [docs/devops-toolchain.md](docs/devops-toolchain.md) |
| Data flow plan | [docs/data-flow.md](docs/data-flow.md) |
| Observability plan | [docs/observability.md](docs/observability.md) |

Read [docs/roadmaps.md](docs/roadmaps.md) before making DevOps,
infrastructure, data-flow, observability, security, incident, rollout, async, or
operator workflow changes.

## What This Demonstrates

| Concern | Mechanism | Key files |
|---|---|---|
| SDLC baseline | GitHub Actions, immutable ECR tags, reproducible Terraform state | `.github/workflows/`, `infra/`, `Makefile` |
| Safe schema rollout | Expand, dual-write, backfill, switch, contract | `db/changelog/`, `apps/backfill-worker/src/aws_sdlc_backfill_worker/main.py` |
| Data export flow | Local and scheduled ECS export job with raw output, manifest, and S3 object storage writes | `apps/data-export-job/src/aws_sdlc_data_export_job/main.py`, `infra/app/object_storage.tf`, `infra/app/workload_jobs.tf` |
| Runtime config | DB-backed `WRITE_MODE` and `READ_MODE` switches | `packages/adapters/src/aws_sdlc_adapters/db/repository.py` |
| Connection pooling | PgBouncer in transaction mode | `compose.yaml`, `db/pgbouncer/pgbouncer.ini` |
| ECS deployment | Build/scan approval followed by rolling app deploy plus one-off Liquibase and worker tasks | `.github/workflows/app-build.yml`, `.github/workflows/app-deploy.yml`, `infra/app/workload_jobs.tf` |
| Infrastructure delivery | Terraform validate, reviewed plan, and separate manual apply | `.github/workflows/infra-plan.yml`, `.github/workflows/infra-apply.yml`, `infra/` |

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
|   |-- data-export-job/ # Data export job
|   `-- order-event-consumer/
|-- packages/
|   |-- core/            # Pure domain entities and ports
|   `-- adapters/        # SQLAlchemy/Postgres adapter implementations
|-- db/                  # Liquibase changelog and Postgres assets
|-- infra/
|   |-- platform/        # VPC, endpoints, Route 53 lookup, GitHub OIDC/CI IAM
|   `-- app/             # ECS, RDS, ALB, ECR, S3, SQS, jobs, observability
|-- scripts/             # Local and CI helper scripts
|-- tests/               # Pytest integration tests
|-- docs/                # Roadmaps, guides, runbooks, and drills
|-- observability/       # Shared local/AWS Grafana, Loki, and Prometheus assets
|-- .github/workflows/   # App and infra workflows
|-- compose.yaml
`-- Makefile
```

Target direction is an evolutionary monorepo with `apps/`, `packages/`,
`infra/`, `db/`, `observability/`, and `docs/` content that has a concrete
owner. See [docs/roadmaps.md](docs/roadmaps.md) for continuation rules.

## Quick Local Path

Prerequisites:

- Docker Desktop
- Optional: VS Code or another editor with Dev Containers support. The
  repository dev container installs the Python, Terraform, Go, Node.js,
  Docker, AWS, and quality-tooling baseline used by the project.
- If you do not use the dev container, install Python 3.14+, `uv`, and optional
  quality tools from their vendor channels as needed for the Make targets you
  run.

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
curl --fail --show-error http://localhost:8000/health
```

Run tests:

```bash
uv sync --all-packages --group dev --group test
make secret-scan
make dependency-audit
make lint-app
make lint-scripts
make lint-docs
make lint-workflows
make lint-dockerfiles
uv run pytest tests/ -v
```

For the full migration walkthrough, read
[docs/local-development.md](docs/local-development.md).

Optional local observability is available through Docker Compose:

```bash
make local-up
# or, after starting the app yourself:
make observability
```

See [docs/observability.md](docs/observability.md) for the Prometheus, Loki,
and Grafana setup.

## CI/CD Shape

GitHub Actions workflows keep security, app, and infrastructure concerns separate:

- `security.yml`: standard secret scanning, docs/workflow/Dockerfile checks, and Python dependency audit on pull requests and `main`.
- `semgrep.yml`: Semgrep Community Edition SAST on pull requests and `main`.
- `infra-plan.yml` / `infra-apply.yml`: Terraform fmt, validate, tflint, checkov, reviewed plan artifact, and separate manual apply of the reviewed plan.
- `app-build.yml` / `app-deploy.yml`: local workload validation, image build, Trivy scan, ECR push, then separate manual migration, ECS service deploy, verification, worker task run, and data export task registration.

Cloud-changing jobs are split so review happens between plan/build-scan and
apply/deploy, without requiring paid environment reviewer gates. AWS
authentication uses GitHub OIDC, not long-lived access keys.

## Later Phases

This repo stays lean on purpose. Current operator-quality work is tracked in
[docs/roadmaps.md](docs/roadmaps.md). Intentionally deferred hardening remains
documented in
[docs/architecture.md#whats-intentionally-omitted](docs/architecture.md#whats-intentionally-omitted).

# aws-sdlc-containers

`aws-sdlc-containers` is an opinionated cloud-native delivery toolkit for
building, running, observing, and shipping portable application workloads. It
does not try to replace proven tools; it assembles industry-standard building
blocks into one repeatable workflow for APIs, workers, event consumers, data
workloads, infrastructure, and operations.

The current runtime implementation is deliberately small: one AWS/ECS stack,
one FastAPI API workload, one backfill workload, one scheduled data export
workload, one Dapr-enabled order event workload host, PgBouncer, Liquibase, one PostgreSQL
database, one app-owned S3 object storage bucket, and split platform/app
Terraform roots. The reusable part is the delivery contract: workload shape,
package boundaries, config/secrets, observability, CI gates, runtime
capabilities, and operator evidence.

## Toolkit Charter

This repo should be a platform toolkit, not a private application framework.

- Use established tools directly: Docker/OCI, FastAPI, SQLAlchemy, Liquibase,
  Dapr, OpenTelemetry, Prometheus, Loki, Tempo, Grafana, Terraform, GitHub
  Actions, Trivy, Semgrep, Gitleaks, Checkov, TFLint, Ruff, Pyright, pytest,
  and `uv`.
- Standardize how those tools fit together: repo layout, shared packages,
  workload contracts, local Compose, container builds, deployment evidence,
  rollback categories, and observability onboarding.
- Keep provider-specific implementation at platform edges: AWS/ECS/RDS/S3/SNS
  details live in Terraform, Dapr components, scripts, workflows, and
  infrastructure adapters, not in domain or application logic.
- Add runtime targets only when a real workload needs them and can satisfy the
  same portable contract.
- Prefer small, explicit conventions over custom abstractions that hide the
  underlying tool.

## Start Here

For a first pass, read this README, then
[docs/architecture-layout.md](docs/architecture-layout.md) for the repo map,
[docs/engineering-loop.md](docs/engineering-loop.md) for the working method,
and [docs/roadmaps.md](docs/roadmaps.md) before changing DevOps,
infrastructure, data, observability, security, incident, rollout, async, or
operator workflow behavior.

For local work, use [docs/local-development.md](docs/local-development.md). For
AWS operations, use [docs/deployment.md](docs/deployment.md),
[infra/README.md](infra/README.md), [docs/runbooks/README.md](docs/runbooks/README.md),
and [docs/drills/README.md](docs/drills/README.md). The fastest no-data
rollback practice is [docs/runbooks/ecs-deploy-rollback.md](docs/runbooks/ecs-deploy-rollback.md)
plus [docs/runbooks/infra-rollback-drill.md](docs/runbooks/infra-rollback-drill.md).

For the grouped documentation map, use [docs/README.md](docs/README.md). It is
the canonical index for platform contracts, runtime docs, delivery docs,
runbooks, and drills.

## What This Demonstrates

| Concern | Mechanism | Key files |
|---|---|---|
| SDLC baseline | GitHub Actions, immutable ECR tags, reproducible Terraform state | `.github/workflows/`, `infra/`, `Makefile` |
| Safe schema rollout | Expand, dual-write, backfill, switch, contract | `db/changelog/`, `apps/backfill_worker/main.py` |
| Data export flow | Local and scheduled ECS export job with raw output, manifest, and S3 object storage writes | `apps/data_export_job/main.py`, `infra/app/object_storage.tf`, `infra/app/workload_jobs.tf` |
| Runtime config | DB-backed `WRITE_MODE` and `READ_MODE` switches | `packages/infrastructure/db/repository.py` |
| Connection pooling | PgBouncer in transaction mode | `compose.yaml`, `db/pgbouncer/pgbouncer.ini` |
| Database portability | PostgreSQL contract with RDS as the current runtime implementation | `docs/data.md`, `db/`, `packages/infrastructure/db/` |
| Dapr event transport | Durable order outbox relayed through Dapr pub/sub on ECS with AWS SNS/SQS underneath | `apps/order_event_consumer/main.py`, `platform/dapr/`, `infra/app/messaging.tf` |
| ECS deployment | Build/scan approval followed by rolling app deploy plus one-off Liquibase and worker tasks | `.github/workflows/app-build.yml`, `.github/workflows/app-deploy.yml`, `infra/app/workload_jobs.tf` |
| Infrastructure delivery | Terraform validate, reviewed plan, and separate manual apply | `.github/workflows/infra-plan.yml`, `.github/workflows/infra-apply.yml`, `infra/` |
| Runtime appendability | Portable workload contract validated before build; runtime guidance stays documented until a second target exists | `platform/workloads.json`, `docs/runtime-toolkit.md`, `scripts/ci/validate_platform_contract.py` |

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
management, background workloads, rollback-safe sequencing, and ECS one-off tasks
without adding unnecessary business complexity.

## Current Project Layout

```text
aws-sdlc-containers/
|-- apps/
|   |-- api/             # FastAPI workload
|   |-- backfill_worker/ # Backfill worker workload
|   |-- data_export_job/ # Data export job
|   `-- order_event_consumer/
|-- packages/
|   |-- domain/          # Pure entities, value objects, and domain events
|   |-- application/     # Use cases, ports, commands/results, outbox contracts
|   `-- infrastructure/  # SQLAlchemy/Postgres and Dapr/S3 adapter implementations
|-- db/                  # Liquibase changelog and Postgres assets
|-- infra/
|   |-- platform/        # VPC, endpoints, Route 53 lookup, GitHub OIDC/CI IAM
|   `-- app/             # ECS, RDS, ALB, ECR, S3, Dapr/SNS/SQS, jobs, observability
|-- platform/            # Platform-owned workload contract and runtime configuration
|   |-- workloads.json   # Workload registry
|   |-- workload.Dockerfile  # Shared workload image build definition
|   `-- dapr/            # Platform-owned Dapr component configuration
|       |-- local/       # Local dev component manifests (LocalStack SNS/SQS)
|       `-- production/  # Production component manifests (real SNS/SQS, secret refs)
|-- scripts/             # CI, release, operator, observability, and data helpers
|-- tests/               # API, application, app-host, data, infrastructure, contract, and script tests
|-- docs/                # Roadmaps, guides, runbooks, and drills
|-- observability/       # Shared local/AWS Grafana, Loki, Tempo, and Prometheus assets
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
Tempo, and Grafana setup.

Optional local Dapr order event transport is available through Docker Compose:

```bash
make dapr-up
```

This starts LocalStack SNS/SQS, the `order-event-consumer` app, and a Dapr
sidecar using the local component manifests under `platform/dapr/local/`.

## CI/CD Shape

GitHub Actions workflows keep security, app, and infrastructure concerns separate:

- `security.yml`: standard secret scanning, docs/workflow/Dockerfile checks, and Python dependency audit on pull requests and `main`.
- `semgrep.yml`: Semgrep Community Edition SAST on pull requests and `main`.
- `infra-plan.yml` / `infra-apply.yml`: Terraform fmt, validate, tflint, checkov, reviewed plan artifact, and separate manual apply of the reviewed plan.
- `app-build.yml` / `app-deploy.yml`: local workload validation, image build, Trivy scan, ECR push, then separate manual migration, ECS service deploy, verification, support workload task run, and data export task registration.

Cloud-changing jobs are split so review happens between plan/build-scan and
apply/deploy, without requiring paid environment reviewer gates. AWS
authentication uses GitHub OIDC, not long-lived access keys.

## Later Phases

This repo stays lean on purpose. Current operator-quality work is tracked in
[docs/roadmaps.md](docs/roadmaps.md). Intentionally deferred hardening remains
documented in
[docs/architecture.md#whats-intentionally-omitted](docs/architecture.md#whats-intentionally-omitted).

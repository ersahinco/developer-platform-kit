# ECS DevOps Monorepo Roadmap

This file is the shared progress tracker for future Codex and human sessions.
Start here before changing structure, CI/CD, infrastructure, data flows, or
observability.

## Current State

The repository is a lean single-stack AWS delivery sandbox:

- One FastAPI app in `apps/api/`.
- One backfill worker in `apps/backfill-worker/`.
- One local and scheduled ECS data export job in `apps/data-export-job/`.
- Pure domain contracts in `packages/core/`.
- SQLAlchemy/Postgres implementations in `packages/adapters/`.
- Liquibase schema migrations in `db/`.
- Single-root Terraform stack in `infra/`.
- One Terraform-managed S3 data hub bucket with raw, curated, and manifest prefixes.
- One EventBridge schedule that runs the ECS data export job.
- GitHub Actions workflows for app validation/deployment and Terraform validation/plan/apply.
- Docker Compose for local Postgres, PgBouncer, app, worker, and optional tools.

The reference workload is a zero-downtime schema migration from
`orders.billing_email` to `order_contact_email` using expand, dual-write,
backfill, read switch, and contract phases.

## Direction

Grow the project into a best-practice ECS DevOps monorepo without breaking the
working safe-rollout demo. The application should stay intentionally simple
until infrastructure, CI/CD, observability, and data flows are reliable enough
to support more complex modules.

The target shape is evolutionary:

```text
aws-sdlc-containers/
|-- apps/
|   |-- api/
|   |-- backfill-worker/
|   `-- data-export-job/
|-- packages/
|   |-- core/
|   `-- adapters/
|-- db/
|-- infra/
|-- docker/
|-- docs/
|-- ops/
|-- security/
|-- scripts/
`-- .github/
```

Do not move everything at once. Each step should preserve local tests, Docker
Compose usage, and the GitHub Actions deployment path.

## Working Principles

- `.kiro/steering/engineering-principles.md` is binding.
- `.idea/architecture.md` is target inspiration, not a one-shot migration.
- Keep public app behavior stable while restructuring internals.
- Prefer small, reversible steps that leave the repo demonstrably working.
- Preserve the safe rollout flow as the core learning artifact.
- Use Prometheus, Loki, and Grafana as the preferred observability target.

## Phase Checklist

### Phase 1: Shared Planning Foundation

- [x] Create `docs/ROADMAP.md`.
- [x] Record current state, target direction, decisions, and phase status.
- [x] Link the roadmap from `README.md`.
- [x] Add ADRs for major decisions.
- [x] Keep this file updated after each structural change.

### Phase 2: Documentation and Operating Model

- [x] Add stable documentation entrypoints under `docs/`.
- [x] Add ADRs only for decisions that guide future implementation.
- [x] Gradually slim `README.md` into a project entrypoint.
- [x] Move long local runbook detail out of `README.md` after adding the replacement docs.
- [x] Keep the detailed operator runbook under `docs/deployment.md`.

### Phase 3: Monorepo Application Shape

- [x] Move `app/` to `apps/api/`.
- [x] Move `worker/` to `apps/backfill-worker/`.
- [x] Extract pure domain code into `packages/core`.
- [x] Extract SQLAlchemy/Postgres adapters into `packages/adapters`.
- [x] Update `uv` workspace members.
- [x] Update Dockerfiles, Docker Compose, tests, Makefile, scripts, and GitHub Actions path filters.
- [x] Run `uv sync --frozen --all-packages --group test`.
- [x] Run `uv run pytest tests/ -v`.
- [x] Verify local Docker Compose smoke flow.

### Phase 4: DevOps Toolchain Hardening

- [x] Add or confirm `.pre-commit-config.yaml`.
- [x] Confirm ruff, pytest, Terraform fmt, tflint, and checkov are easy to run locally.
- [x] Preserve manual AWS deployment confirmations in GitHub Actions.
- [x] Keep Trivy image scanning before image push.
- [x] Document Bitbucket Pipelines equivalents without adding a second CI implementation.
- [x] Add rollback and failure recovery checkpoints to the deployment runbook.

### Phase 5: Data Flow Track

- [x] Keep Liquibase expand/contract as the first data reliability example.
- [x] Design data hub v1 before adding resources.
- [x] Add first local data export job before S3/EventBridge resources.
- [x] Add S3 raw/curated convention when a real export job exists.
- [x] Add one ECS data job and scheduled EventBridge trigger.
- [x] Avoid Kafka, Glue, Lake Formation, and multi-account data platforms until the base flow is reliable.

### Phase 6: Observability Track

- [x] Add app `/metrics` endpoint.
- [x] Add local Prometheus scrape config.
- [x] Add local Loki ingestion.
- [x] Add Grafana provisioning and one dashboard.
- [x] Verify the observability stack locally before adding AWS deployment.
- [x] Document CloudWatch as the AWS-native tradeoff, not the default target.

### Phase 7: Infrastructure Track

- [x] Keep single-root Terraform until multiple lifecycle layers are justified.
- [x] Continue using community AWS modules where they fit.
- [x] Keep optional features explicit: WAF, VPC endpoints, ECS Exec, observability, and data hub.
- [x] Split Terraform into stacks only when lifecycle boundaries become real.

## Next Session Should Start Here

1. Read this file, `README.md`, `docs/architecture.md`, and `.kiro/steering/engineering-principles.md`.
2. Check `git status --short` before editing. The `.gitignore` file may contain user-owned changes.
3. Pick exactly one unchecked phase item.
4. Make the smallest change that advances that item.
5. Run the relevant verification from the checklist.
6. Update this file before ending the session.

Recommended next pick: keep Phase 5 stable and move to a small AWS-native
observability or operator-quality slice only if it has a concrete acceptance
test. Do not add Glue, Athena, Kafka, or multi-account data platform resources.

## Documentation Ownership

- `README.md` is the short project index and should not become a runbook.
- `docs/ROADMAP.md` is the cross-session tracker and decision checklist.
- `docs/deployment.md` is the detailed AWS operator runbook.
- `docs/architecture.md` keeps the long-form rationale and intentionally
  omitted hardening work.
- `docs/*` files are stable topic entrypoints. Do not add a new docs file
  unless there is real content and a clear owner.

## Decisions and Assumptions

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-29 | Use `docs/ROADMAP.md` as the cross-session tracker. | It is visible, durable, and easy for humans and Codex sessions to find. |
| 2026-04-29 | Use an evolutionary monorepo restructure. | The current stack works and demonstrates safe rollout; preserving that value matters more than a clean tree in one change. |
| 2026-04-29 | Keep one Terraform root for now. | Multiple stacks add lifecycle complexity before the project has a real need for separate layers. |
| 2026-04-29 | Prefer Prometheus, Loki, and Grafana for observability. | This matches the intended DevOps demo and interview story while keeping CloudWatch as a documented tradeoff. |
| 2026-04-29 | Keep app complexity low until platform flows are reliable. | This template is about ECS delivery, data safety, and DevOps practices, not domain feature breadth. |
| 2026-04-29 | Add the data hub as one private S3 bucket before ECS scheduling. | The export job already has raw and manifest paths, and the bucket convention can be reviewed independently before adding job runtime permissions and EventBridge. |
| 2026-04-29 | Schedule exactly one S3 data export job before adding data-platform services. | A daily ECS task proves the complete data-job lifecycle while avoiding Glue, Athena, Kafka, or multi-account complexity. |

## Completed Work Log

| Date | Work | Verification |
|---|---|---|
| 2026-04-29 | Added shared roadmap, docs entrypoints, and ADRs for the first organizational slice. | Documentation-only change; checked file list and git diff. |
| 2026-04-29 | Slimmed `README.md` into a project entrypoint and moved the local walkthrough into `docs/local-development.md`. | Documentation-only change; checked markdown file list, git diff, and whitespace. |
| 2026-04-29 | Confirmed pre-commit exists and added `ruff` to the root dev dependency group for reproducible local lint/format commands. | Ran `uv add --dev 'ruff>=0.4.4'`; follow-up lint verification tracked in this session. |
| 2026-04-29 | Confirmed manual GitHub Actions deploy/apply gates, Trivy image scanning, and Bitbucket Pipelines equivalence notes. | Inspected `.github/workflows/app.yml`, `.github/workflows/infra.yml`, and `docs/devops-toolchain.md`. |
| 2026-04-29 | Added phase-by-phase rollback and failure recovery checkpoints to the deployment runbook. | Documentation-only deployment change; checked whitespace on edited files. |
| 2026-04-29 | Added `docs/data-flow.md` with the current migration flow and a deliberately small data hub v1 design. | Documentation-only data-flow change; no AWS resources added. |
| 2026-04-29 | Added local observability v1: app `/metrics`, optional Compose services for Prometheus/Loki/Promtail/Grafana, and a provisioned Grafana app overview dashboard. | Focused verification tracked in this session; full local stack startup remains the remaining Phase 6 verification item. |
| 2026-04-29 | Verified the local observability stack and added `make observability` / `make observability-stop`. | App `/health` and `/metrics` passed, Prometheus target was `up`, Loki labels were present, Grafana health was `ok`, and Docker profile services were running. |
| 2026-04-29 | Moved deployable workloads from `app/` and `worker/` to `apps/api/` and `apps/backfill-worker/`. | Updated workspace, Compose, Makefile, GitHub Actions, tests, and docs. Verified imports, image builds, app health, ruff, frozen sync, and full pytest: 22 passed, 3 skipped. |
| 2026-04-29 | Extracted pure domain code to `packages/core` and SQLAlchemy/Postgres implementations to `packages/adapters`. | Refreshed `uv.lock`; ran `uv sync --frozen --all-packages --group test`, `uv run ruff check apps/ packages/ tests/ scripts/`, API import smoke check, `docker compose build app`, rebuilt app `/health` and `/metrics`, and full pytest: 22 passed, 3 skipped. |
| 2026-04-29 | Added `infra/README.md` to document the single Terraform root, concern-based file map, community-module policy, optional-extension boundaries, and future split criteria. | No Terraform resources changed. Ran `terraform fmt -check -recursive infra/` and `terraform -chdir=infra validate`. |
| 2026-04-29 | Added root `.dockerignore` for repo-root API image builds. | Excludes local env files, Terraform state/plans, caches, and runtime noise from Docker build context. Verified with `docker compose build app`. |
| 2026-04-29 | Added local data export job under `apps/data-export-job` with raw CSV output and success manifest paths shaped like the future data hub. | Refreshed `uv.lock`; ran `uv sync --frozen --all-packages --group test`, `uv run ruff check apps/ packages/ tests/ scripts/`, focused data export tests, `docker compose build data-export-job`, Compose data export smoke, and full pytest: 24 passed, 3 skipped. |
| 2026-04-29 | Cleaned up the post-restructure sharp edges: unified worker Docker build on the root workspace lock, removed unused `testcontainers` and pytest marker, streamed the data export instead of buffering all rows, clarified data-export deployment scope, and documented docs ownership. | Ran `uv lock`, `uv sync --frozen --all-packages --group test`, `uv run ruff check apps/ packages/ tests/ scripts/`, `docker compose build app worker data-export-job`, focused data export tests, full pytest: 24 passed, 3 skipped, and Compose worker/data-export smokes. |
| 2026-04-29 | Consolidated long-form docs under `docs/`, removed personal developer workflow notes, renamed infra/CI files for clearer ownership, and aligned runtime package names with app directories. | Ran `uv lock`, `uv sync --frozen --all-packages --group test`, `uv run ruff check apps/ packages/ tests/ scripts/`, API import smoke, `docker compose build app worker data-export-job`, full pytest: 24 passed, 3 skipped, app `/health` and `/metrics` smokes, `terraform fmt -check -recursive infra/`, and `terraform -chdir=infra validate`. |
| 2026-04-29 | Added the AWS data hub bucket with raw, curated, and manifest prefix convention, plus scoped GitHub Actions Terraform permissions and operator outputs. | Ran `terraform fmt -check -recursive infra/`, `terraform -chdir=infra validate`, and `checkov -d infra --framework terraform --config-file infra/.checkov.yaml`. |
| 2026-04-29 | Promoted the data export job to a scheduled ECS task that uploads raw CSV and manifest objects to S3, and added CI image promotion/registration for the job. | Ran `uv lock`, `uv sync --frozen --all-packages --group test`, focused data export tests, full pytest: 26 passed, 3 skipped, ruff, `docker compose build data-export-job`, `terraform fmt -check -recursive infra/`, `terraform -chdir=infra validate`, and Checkov: 220 passed, 0 failed. |
| 2026-04-29 | Added repo-wide Pyright type checking for app, packages, tests, and scripts; fixed nullable runtime configuration seams and typed shared test helpers. | Ran `uv sync --frozen --all-packages --group dev --group test`, `uv run ruff check apps/ packages/ tests/ scripts/`, `uv run pyright`, and `uv run pytest tests/ -v`. |

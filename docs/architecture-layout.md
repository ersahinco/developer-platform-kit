# Architecture Layout

This document explains how the repository is laid out today and why each
boundary exists. It is intentionally pragmatic: it should help a developer or
operator find the owner of a behavior quickly, change one coherent slice, and
avoid adding duplicate paths.

For design rationale, read `docs/architecture.md`. For how to continue work,
read `docs/engineering-loop.md`.

## Layout Principles

- Keep standard tool entrypoints at the repo root: `pyproject.toml`, `uv.lock`,
  `compose.yaml`, `Makefile`, `.dockerignore`, and `.pre-commit-config.yaml`.
- Group files by control boundary, not by generic technology buckets.
- Keep app complexity small while the delivery lifecycle stays the main lesson.
- Add folders only when there is real behavior and a clear owner.
- Prefer one canonical doc per topic; remove stale aliases when paths move.
- Split cloud-changing automation by review boundary: build before deploy, plan
  before apply.
- Keep scripts small and explicit; use maintained tools for checks.

## Current Tree

```text
aws-sdlc-containers/
|-- .github/workflows/       # CI, security, app build/deploy, infra plan/apply
|-- apps/                    # Runtime entrypoints
|   |-- api/
|   |-- backfill-worker/
|   |-- data-export-job/
|   `-- order-event-consumer/
|-- packages/                # Shared modular-monolith code
|   |-- core/
|   `-- adapters/
|-- db/                      # Liquibase, bootstrap SQL, PgBouncer image/config
|-- infra/                   # Terraform roots split by lifecycle
|   |-- platform/
|   `-- app/
|-- observability/           # Portable Prometheus, Loki, Promtail, Grafana assets
|-- scripts/                 # CI and operator helpers
|-- tests/                   # Pytest integration and contract checks
|-- docs/                    # Canonical docs, runbooks, and drills
|-- compose.yaml
|-- Makefile
|-- pyproject.toml
`-- uv.lock
```

## End-to-End Control Flow

```text
developer change
  |
  v
GitHub pull request
  |
  +--> security.yml / semgrep.yml
  |       secret scan, dependency audit, docs, workflow, Dockerfile checks, SAST
  |
  +--> app-build.yml
  |       uv sync, lint/type/test, local workload validation, Docker build,
  |       Trivy scan, immutable ECR image tags
  |
  +--> infra-plan.yml
          terraform fmt/validate/tflint/checkov, reviewed plan artifact

manual cloud change
  |
  +--> infra-apply.yml
  |       applies a reviewed Terraform plan
  |
  `--> app-deploy.yml
          runs Liquibase, updates ECS service, verifies deploy, runs support jobs
```

This split is deliberate. The repo demonstrates reviewable cloud operations
without relying on hidden local state or long-lived AWS keys. AWS access comes
through GitHub OIDC.

## GitHub Workflows

`.github/workflows/` is organized by responsibility:

| Workflow | Owner boundary |
|---|---|
| `security.yml` | Cross-cutting repository hygiene: secrets, dependency audit, docs, workflows, Dockerfiles. |
| `semgrep.yml` | SAST using Semgrep Community Edition. |
| `app-build.yml` | Application validation, image build, image scan, and push. |
| `app-deploy.yml` | Manual ECS deployment, migration task, verification, and support jobs. |
| `infra-plan.yml` | Terraform quality gates and reviewed plan creation. |
| `infra-apply.yml` | Manual apply of reviewed Terraform changes. |

Critical rule: do not merge build/deploy or plan/apply back into one workflow
unless the replacement still preserves a human review point before AWS changes.

## Applications

Each folder under `apps/` is a runtime entrypoint with its own Dockerfile and
`pyproject.toml`.

| App | Purpose | Import package |
|---|---|---|
| `apps/api` | FastAPI app, health/readiness/metrics, order APIs, runtime mode switches, outbox writes. | `aws_sdlc_api` |
| `apps/backfill-worker` | One-off safe-rollout worker for historical `billing_email` migration. | `aws_sdlc_backfill_worker` |
| `apps/data-export-job` | Scheduled export job for operational data and manifests. | `aws_sdlc_data_export_job` |
| `apps/order-event-consumer` | Outbox relay and SQS consumer for `order.created.v1`. | `aws_sdlc_order_event_consumer` |

Keep app folders thin. Runtime wiring, settings, command entrypoints, and HTTP
schemas belong here. Reusable domain concepts belong in `packages/core`;
database, queue, and storage implementations belong in `packages/adapters`.

## Shared Packages

`packages/core` is pure Python domain code:

- entities and value objects
- ports
- idempotency contracts
- order submission behavior
- outbox and receipt models

`packages/adapters` implements the outside world:

- SQLAlchemy/Postgres repositories
- runtime config storage
- SQS publishing/consuming support
- S3/data hub access where needed

Critical rule: `packages/core` should not import FastAPI, SQLAlchemy, boto3, or
environment-specific settings. If that line blurs, the modular-monolith shape
becomes harder to test and explain.

## Database

`db/` owns schema evolution and database-adjacent runtime assets:

- `db/changelog/`: Liquibase migration sequence.
- `db/sql/bootstrap.sql`: local bootstrap SQL.
- `db/pgbouncer/`: PgBouncer image/config used by local and ECS patterns.
- `db/Dockerfile`: Liquibase image packaging.

The main reliability story remains the expand/dual-write/backfill/switch/
contract migration from `orders.billing_email` to `order_contact_email`.

Critical rule: schema changes should come with the app, worker, tests, and
runbook changes required to operate them safely. Do not add DDL in isolation
when behavior depends on runtime rollout sequencing.

## Infrastructure

`infra/` has no root of its own. Terraform is split by lifecycle:

| Root | Owns | Does not own |
|---|---|---|
| `infra/platform` | VPC, subnet tiers, endpoints, Route 53/account lookups, GitHub OIDC and CI IAM. | RDS, ECS workloads, ALB, app queues, data buckets, observability services. |
| `infra/app` | RDS, ECS, ECR, ALB/API edge, WAF association, S3 data hub, SQS, jobs, app IAM, CloudWatch alarms, optional observability. | VPC creation, GitHub OIDC identity, app-independent bootstrap. |

The split is not environment promotion. It is lifecycle separation inside one
lean AWS stack. Keep it that way until separate environments or stacks have a
real operating requirement.

Terraform file naming is capability-oriented:

- `compute_ecs.tf`
- `database.tf`
- `edge.tf`
- `messaging.tf`
- `object_storage.tf`
- `observability.tf`
- `runtime_identity.tf`
- `workload_jobs.tf`

Critical rule: avoid scattering one capability across many tiny Terraform
files. A reader should be able to find the owner of a queue, bucket, ECS task,
or alarm without chasing generic `iam.tf`, `cloudwatch.tf`, and `data.tf`
fragments.

## Observability

`observability/` contains portable local/AWS assets:

- Prometheus scrape config and alert rules.
- Loki config.
- Promtail config.
- Grafana datasources, dashboards, and provisioning.

AWS-specific rendering templates live under
`infra/app/templates/observability/` because ECS storage/service discovery can
differ from local Compose.

Critical rule: dashboards and alerts should answer operator questions:

- Is the app healthy?
- Did deploy verification pass?
- Is the database under pressure?
- Are export jobs succeeding?
- Are messages stuck or in DLQ?

Avoid decorative dashboards and metrics that do not drive an action.

## Scripts

`scripts/` contains two kinds of helpers:

- `ci_*`: GitHub Actions helpers for ECS task registration, service deploys,
  polling, and assertions.
- Operator/local helpers: `db_tunnel.sh`, `db_exec.sh`, `db_seed_tunnel.sh`,
  `seed_data.py`, and `verify_post_deploy.py`.

Critical rule: scripts should hide awkward shell quoting or AWS CLI plumbing,
not business policy. If a behavior is important enough to test, put the policy
in Python or Terraform where it can be checked directly.

## Tests

`tests/` is integration-heavy by design because the project demonstrates
delivery and rollout behavior.

Test ownership:

- API behavior and operational endpoints.
- Migration phase invariants.
- Backfill worker idempotency and checkpointing.
- Data export output and manifest behavior.
- Database URL/config safety.
- Order outbox, order events, and consumer behavior.
- Post-deploy verification script behavior.
- Schema contract checks.

Critical rule: tests should preserve rollout confidence, not mirror
implementation files one-to-one. Add tests around contracts, failure modes, and
operator-visible behavior before adding broad unit-test scaffolding.

## Local Automation

`Makefile` is the local control plane. It should expose memorable commands and
delegate complicated implementation to standard tools or small scripts.

Important targets:

- `make dev`
- `make local-up`
- `make migrate`
- `make seed`
- `make data-export`
- `make test`
- `make lint`
- `make fmt`
- `make infra-platform-plan`
- `make infra-app-plan`
- `make app-deploy`
- `make post-deploy-verify`

Critical rule: keep root automation discoverable. Avoid adding parallel
one-off shell commands to docs when a Make target already owns the workflow.

## Documentation

`docs/` owns canonical project knowledge:

- `engineering-loop.md`: how to continue work safely.
- `roadmaps.md`: current state, decisions, continuation guide.
- `architecture.md`: design rationale and intentionally omitted work.
- `architecture-layout.md`: repository/control-boundary map.
- `deployment.md`: AWS operator runbook.
- `local-development.md`: local safe-rollout walkthrough.
- `devops-toolchain.md`: quality gates and CI/CD conventions.
- `data-flow.md`: migration and data export flow.
- `observability.md`: metrics/logging/dashboard direction.
- `runbooks/`: operator actions for real incidents.
- `drills/`: practice scenarios.

Critical rule: do not add a new doc for every thought. Add or edit the one doc
that owns the topic, and delete stale notes when their content becomes
canonical elsewhere.

## Lean Expansion Rules

Add new structure only when all of these are true:

1. The behavior exists or is about to exist.
2. The owner is obvious.
3. The verification path is clear.
4. The docs can point to one canonical place.
5. The change reduces future confusion more than it adds surface area.

Do not add:

- empty folders for future architecture
- duplicate CI implementations
- a second deployment path without a real user
- generic Terraform files that hide ownership
- new app modules that only wrap one function
- business features that do not exercise the delivery lifecycle

## Critical Current Shape Assessment

The current structure is strong because it has real vertical examples:

- safe database rollout
- one-off ECS tasks
- scheduled data export
- async queue processing
- split infra lifecycle
- local and CI quality gates
- runbooks tied to actual failure modes

The main risks are the usual risks of a template that is becoming capable:

- Too many docs can reintroduce ambiguity if ownership is not enforced.
- Terraform can become harder to scan if capability files start sharing hidden
  IAM, alarm, or data-source assumptions.
- App modules can become over-layered if every small behavior becomes a new
  abstraction.
- CI scripts can turn into a second deployment framework if policy accumulates
  there instead of in workflows, Terraform, or tested Python.
- Observability can become noise if dashboards are not tied to operator
  decisions.

Use these risks as guardrails. The next best change is usually the one that
removes ambiguity from an existing path, not the one that adds a new subsystem.

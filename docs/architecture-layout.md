# Architecture Layout

This document explains how the repository is laid out today and why each
boundary exists. It is intentionally pragmatic: it should help a developer or
operator find the owner of a behavior quickly, change one coherent slice, and
avoid adding duplicate paths.

For design rationale, read `docs/architecture.md`. For how to continue work,
read `docs/engineering-loop.md`.

## Layout Principles

- Treat the repo as a delivery toolkit: standardize how proven tools are wired
  together, not as a place to invent replacement frameworks.
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
|   |-- backfill_worker/
|   |-- data_export_job/
|   `-- order_event_consumer/
|-- packages/                # Shared modular-monolith code
|   |-- domain/
|   |-- application/
|   `-- infrastructure/
|-- db/                      # Liquibase, bootstrap SQL, PgBouncer image/config
|-- docker/                  # Shared workload image build definition
|-- infra/                   # Terraform roots split by lifecycle
|   |-- platform/
|   `-- app/
|-- platform/                # Machine-readable portable workload and runtime contracts
|-- observability/           # Portable Prometheus, Loki, Promtail, Grafana assets
|-- scripts/                 # Grouped CI, release, operator, data, and observability helpers
|-- tests/                   # Pytest behavior, contract, script, and runtime checks
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

Each folder under `apps/` is a runtime entrypoint with its own `pyproject.toml`.
Workloads share `platform/workload.Dockerfile`, with build args declared in
`platform/workloads.json`.

| App | Purpose | Import package |
|---|---|---|
| `apps/api` | FastAPI app, health/readiness/metrics, order APIs, runtime mode switches, outbox writes. | `api` |
| `apps/backfill_worker` | One-off safe-rollout worker for historical `billing_email` migration. | `backfill_worker` |
| `apps/data_export_job` | Scheduled export job for operational data and manifests. | `data_export_job` |
| `apps/order_event_consumer` | Dapr-enabled outbox relay and subscriber for `order.created.v1`. | `order_event_consumer` |

Keep app folders thin. Runtime wiring, settings, command entrypoints, and HTTP
schemas belong here. Reusable domain concepts belong in `packages/domain`,
use cases and ports belong in `packages/application`, and database, Dapr, queue,
and storage implementations belong in `packages/infrastructure`.

The source tree is intentionally flat. Do not add `src/` or generated package
name wrappers such as `aws_sdlc_api` or `aws_sdlc_application`. The folder is
the import package:

- `apps/api/main.py` imports as `api.main`
- `apps/order_event_consumer/main.py` imports as `order_event_consumer.main`
- `packages/domain/order.py` imports as `domain.order`
- `packages/application/order_submission.py` imports as
  `application.order_submission`
- `packages/infrastructure/db/repository.py` imports as
  `infrastructure.db.repository`

## Shared Packages

`packages/domain` is pure Python domain code:

- entities and value objects
- domain events and pure rules

`packages/application` is the application layer:

- use cases and orchestration
- stable ports such as repositories and config stores
- command/result objects
- outbox dispatch and receipt contracts

`packages/infrastructure` implements the outside world:

- SQLAlchemy/Postgres repositories
- runtime config storage
- Dapr pub/sub publishing support
- S3/data hub access where needed

Critical rule: `packages/domain` and `packages/application` should not import
FastAPI, SQLAlchemy, boto3, Dapr adapters, or environment-specific app settings.
If that line blurs, the modular-monolith shape becomes harder to test and
explain.

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
| `infra/app` | RDS, ECS, ECR, ALB/API edge, WAF association, S3 data hub, Dapr-backed SNS/SQS, jobs, app IAM, CloudWatch alarms, optional observability. | VPC creation, GitHub OIDC identity, app-independent bootstrap. |

The split is not environment promotion. It is lifecycle separation inside one
lean AWS stack. Keep it that way until separate environments or stacks have a
real operating requirement.

Terraform file naming is capability-oriented:

- `compute_ecs.tf`
- `database.tf`
- `ecr.tf`
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

`observability/` contains portable local analysis assets:

- Prometheus scrape config and alert rules.
- Loki config.
- Promtail config.
- Grafana datasources, dashboards, and provisioning.

AWS runtime telemetry wiring lives in `infra/app/observability.tf` as the ADOT
sidecar container contract. Do not add AWS-specific dashboard rendering
templates unless a hosted visualization layer is intentionally reintroduced.

Critical rule: dashboards and alerts should answer operator questions:

- Is the app healthy?
- Did deploy verification pass?
- Is the database under pressure?
- Are export jobs succeeding?
- Are messages stuck or in DLQ?

Avoid decorative dashboards and metrics that do not drive an action.

## Scripts

`scripts/` is grouped by caller and operating context:

- `scripts/ci/`: GitHub Actions helpers for ECS task registration, service
  deploys, polling, image mutation, and assertions.
- `scripts/operator/`: local/operator tunnels and database access helpers.
- `scripts/release/`: post-deploy verification used by the reviewed App Deploy
  workflow and local smoke checks.
- `scripts/observability/`: cloud traffic, release/incident evidence, and
  delivery verification.
- `scripts/data/`: local and remote data setup helpers.

Critical rule: scripts should hide awkward shell quoting or AWS CLI plumbing,
not business policy. If a behavior is important enough to test, put the policy
in Python or Terraform where it can be checked directly.

Scripts should also avoid becoming a shadow deployment framework. Prefer small
helpers around standard tools and keep the durable contract in workflows,
Terraform, workload metadata, or tested Python.

## Tests

`tests/` is integration-heavy by design because the project demonstrates
delivery and rollout behavior. It is grouped by durable behavior area rather
than mirrored source-file names:

- `tests/api/`: API behavior, operational endpoints, telemetry, and runtime
  mode behavior.
- `tests/application/`: pure application/domain behavior such as order
  submission, domain events, and outbox dispatch.
- `tests/apps/`: workload-host behavior that crosses app wiring boundaries,
  such as the Dapr order event runtime.
- `tests/data/`: backfill, export, schema, and database configuration behavior.
- `tests/infrastructure/`: concrete adapter behavior such as SQLAlchemy
  repository contracts.
- `tests/contracts/`: static contracts for workflows, infrastructure,
  dashboards, schemas, and docs.
- `tests/scripts/`: pragmatic script behavior tests for release and
  observability helpers.
- `tests/runtime/`: opt-in container conformance tests that build declared
  workload images and prove health, readiness, metrics, logs, config, secrets,
  and job success from the outside.

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

`docs/` owns canonical project knowledge. The grouped documentation map lives
in `docs/README.md`; keep detailed ownership there so this architecture layout
can focus on repo boundaries.

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

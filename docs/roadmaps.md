# Roadmaps

This is the single roadmap, continuation guide, and roadmap history for the
repository. The older `docs/ROADMAP*.md` files were consolidated here so future
sessions have one place to read before changing DevOps, infrastructure,
data-flow, observability, security, incident, rollout, async, or operator
workflow behavior.

## Current Status

The repository is a lean AWS delivery sandbox around one intentionally simple
order/customer domain:

- FastAPI API with `/health`, `/ready`, `/metrics`, request ID propagation,
  runtime `READ_MODE` and `WRITE_MODE` switches, and `order.created.v1` SQS
  publishing.
- Checkpointed backfill worker with bounded pause/resume runs.
- Scheduled ECS data export job with raw CSV output, validated manifests, and
  S3 data hub publishing.
- Single-root Terraform stack for ECS, RDS, ALB, ECR, S3 data hub, SQS order
  events, EventBridge, CloudWatch alarms, and GitHub OIDC.
- Local Prometheus, Loki, Promtail, and Grafana observability profile.
- Runbooks for deployment rollback, app health, app edge symptoms, RDS
  pressure, data export failures, app dependency-readiness drills, and order
  event queue failures.
- Local and CI checks for Ruff, Pyright, pytest, Terraform, TFLint, Checkov,
  CodeQL, Trivy, dependency audit, secret scan, workflow policy, Dockerfile
  policy, docs links, and shell syntax.

The reference workload remains the zero-downtime schema evolution from
`orders.billing_email` to `order_contact_email`: expand, dual-write, backfill,
switch reads, new writes, and contract.

## Continuation Rules

1. Check `git status --short` before editing and preserve user-owned worktree
   changes.
2. Pick one coherent operator or platform slice.
3. Make the smallest complete change that preserves the simple domain and
   single-stack operating model.
4. Verify with the relevant local checks.
5. Update this file when the change affects roadmap status or decisions.
6. Commit only the related files.

Next session note: the user intends to ask for a comparison between
`.idea/architecture.md` and the current repository status. Start that comparison
from this file, `README.md`, `docs/architecture.md`, `docs/deployment.md`,
`docs/observability.md`, `docs/data-flow.md`, and the live file tree.

## Documentation Ownership

- `README.md` is the short project index.
- `docs/roadmaps.md` is the single roadmap and history file.
- `docs/deployment.md` is the detailed AWS operator runbook.
- `docs/local-development.md` is the local migration walkthrough.
- `docs/architecture.md` keeps long-form rationale and intentionally omitted
  hardening work.
- `docs/observability.md` explains Prometheus, Loki, Grafana, and CloudWatch
  signals.
- `docs/data-flow.md` explains the current migration and data export flow.
- New `ops/` or `security/` files should appear only with concrete owned
  content.

## Active Direction

V5 is complete. The next work should be driven by a fresh comparison against
`.idea/architecture.md` and should stay honest about what is already built:

- Keep the repo single-stack until separate lifecycle boundaries are real.
- Keep the app domain simple unless a platform workflow needs a concrete
  example.
- Prefer drills, verification, runbooks, and narrow policy checks over broad
  placeholder trees.
- Add new workloads only when they demonstrate a complete production operator
  story with tests, metrics/logs, failure handling, and rollback or replay
  guidance.

## Consolidated Phase History

### V1: Baseline Monorepo, Data Flow, Observability

- [x] Created the shared roadmap and initial docs entrypoints.
- [x] Slimmed `README.md` into a project entrypoint and moved local walkthrough
  detail into `docs/local-development.md`.
- [x] Preserved manual GitHub Actions deploy/apply gates and Trivy image
  scanning.
- [x] Added rollback and failure recovery checkpoints to deployment docs.
- [x] Moved deployable workloads to `apps/api`, `apps/backfill-worker`, and
  `apps/data-export-job`.
- [x] Extracted pure domain code into `packages/core` and SQLAlchemy/Postgres
  implementations into `packages/adapters`.
- [x] Kept a single Terraform root and documented extension boundaries in
  `infra/README.md`.
- [x] Added local data export job and promoted it to scheduled ECS/S3 export.
- [x] Added local Prometheus, Loki, Promtail, and Grafana.
- [x] Added repo-wide Pyright type checking.

### V2: Operator Signals, Runbooks, Security Gates

- [x] Added CloudWatch alarms for scheduled data export failures.
- [x] Added ECS service health, ALB target 5xx/latency, and RDS pressure alarms.
- [x] Added concrete runbooks under `ops/runbooks/`.
- [x] Added secret scan, dependency audit, and CodeQL gates.
- [x] Added Dependabot policies for Python dependencies and GitHub Actions.
- [x] Confirmed ECR scan-on-push and Trivy-before-push policy.
- [x] Aligned pre-commit, Make, and CI quality gates.
- [x] Added data export success and freshness signals.
- [x] Kept Glue, Athena, Kafka, Lake Formation, SBOM generation, and
  `security/exceptions.yaml` deferred until they have real consumers.

### V3: Quality Gate Completeness And Documentation Hygiene

- [x] Added zero-dependency shell syntax checks for operator scripts.
- [x] Normalized roadmap references.
- [x] Added local Markdown link checker and wired it into Make, pre-commit, and
  CI.
- [x] Kept `.idea/architecture.md` as inspiration rather than a one-shot
  migration map.

### V4: Production Runtime Patterns

- [x] Compared the repo against `.idea/architecture.md` and recorded deferred
  implementation decisions.
- [x] Added `.editorconfig`.
- [x] Added dependency-free workflow policy checks for path-filter self-coverage
  and OIDC confirmation gates.
- [x] Added database-backed `/ready` readiness and request ID propagation.
- [x] Strengthened data export manifests with byte count and SHA-256 validation.
- [x] Added a Grafana readiness-failure stat for `/ready` 5xx responses.
- [x] Added Dockerfile policy checks for base-image tags, app multi-stage
  builds, and non-root runtime users.
- [x] Added `BACKFILL_MAX_BATCHES` for bounded, checkpointed backfill runs.
- [x] Continued deferring packages, Terraform splits, `deploy/`, and
  `security/` trees until they have concrete ownership.

### V5: Incident Drills, Rollout Verification, Async Events, Consolidation

- [x] Added an app dependency-readiness incident drill.
- [x] Added read-only runtime mode endpoints and a post-deploy verifier for
  `/health`, `/ready`, `/metrics`, runtime modes, and ECS task/image metadata.
- [x] Consolidated roadmap guidance into `docs/roadmaps.md`.
- [x] Added SQS FIFO-backed `order.created.v1` publishing from the API with an
  order-ID idempotency key.
- [x] Added SQS queue, DLQ, DLQ alarm, app IAM permission, publish metrics,
  tests, and an order event queue failure runbook.

## Decisions And Assumptions

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-29 | Keep one Terraform root until lifecycle boundaries become real. | Multiple stacks add naming, state, workflow, and documentation overhead before the project has repeated infrastructure shape. |
| 2026-04-29 | Use an evolutionary monorepo restructure. | The working safe-rollout demo should remain usable while the repo shape improves. |
| 2026-04-29 | Prefer Prometheus, Loki, and Grafana locally while using CloudWatch for AWS-native alarms. | The repo demonstrates both local open-source observability and AWS operator signals without forcing a managed observability stack. |
| 2026-04-29 | Keep the application domain simple. | The value is in ECS delivery, data safety, DevOps practices, and operator maturity, not broad business features. |
| 2026-04-29 | Add folders only with real content. | Empty `ops/`, `security/`, `deploy/`, or package placeholders create ownership noise without improving operations. |
| 2026-04-29 | Prefer narrow policy checks over broad unused policy trees. | Small dependency-free checks protect concrete invariants with low maintenance cost. |
| 2026-04-29 | Use one SQS-backed order event before adding a consumer app. | The event, idempotency key, queue, DLQ, metrics, tests, and runbook prove async behavior without a placeholder runtime. |
| 2026-04-29 | Consolidate all roadmap history under `docs/roadmaps.md`. | Future sessions need one source of truth before comparing the repo to `.idea/architecture.md`. |

## Completed Work Log

| Date | Work | Verification |
|---|---|---|
| 2026-04-29 | Added shared roadmap, docs entrypoints, and ADRs for the first organizational slice. | Documentation-only change; checked file list and git diff. |
| 2026-04-29 | Slimmed `README.md` into a project entrypoint and moved the local walkthrough into `docs/local-development.md`. | Documentation-only change; checked markdown file list, git diff, and whitespace. |
| 2026-04-29 | Confirmed manual GitHub Actions deploy/apply gates, Trivy image scanning, and Bitbucket Pipelines equivalence notes. | Inspected app/infra workflows and `docs/devops-toolchain.md`. |
| 2026-04-29 | Added phase-by-phase rollback and failure recovery checkpoints to the deployment runbook. | Documentation-only deployment change; checked whitespace on edited files. |
| 2026-04-29 | Added `docs/data-flow.md` with the current migration flow and a deliberately small data hub v1 design. | Documentation-only data-flow change; no AWS resources added. |
| 2026-04-29 | Added and verified local observability v1 with `/metrics`, Prometheus, Loki, Promtail, Grafana, and Make targets. | App, Prometheus, Loki, and Grafana smokes passed. |
| 2026-04-29 | Moved workloads into `apps/` and extracted `packages/core` plus `packages/adapters`. | Ran workspace sync, Ruff, Docker builds, app smokes, and pytest. |
| 2026-04-29 | Added `infra/README.md` and root `.dockerignore`. | Ran Terraform fmt/validate and Docker build verification. |
| 2026-04-29 | Added local data export job and promoted it to scheduled ECS/S3 export. | Ran lock/sync, Ruff, focused/full tests, Docker build, Terraform fmt/validate, and Checkov. |
| 2026-04-29 | Added repo-wide Pyright type checking. | Ran sync, Ruff, Pyright, and pytest. |
| 2026-04-29 | Added CloudWatch alarms for Scheduler, ALB target health, ALB edge symptoms, and RDS pressure. | Ran Terraform fmt/validate, TFLint, Checkov, and docs checks. |
| 2026-04-29 | Added runbooks for data export failure, app unhealthy targets, app edge symptoms, RDS pressure, and ECS deploy rollback. | Ran docs checks and path-scoped whitespace checks. |
| 2026-04-29 | Added secret scan, dependency audit, CodeQL, Dependabot updates, and quality gate alignment. | Ran focused tests, Ruff, Pyright, pytest, workflow parsing, and docs checks. |
| 2026-04-29 | Added data export success metric filter and freshness alarm. | Ran Terraform fmt/validate, TFLint, Checkov, and docs checks. |
| 2026-04-29 | Added shell syntax and Markdown link checks. | Ran direct, Make, pre-commit, CI-policy, and formatting checks. |
| 2026-04-29 | Added `.editorconfig`, workflow policy checks, API readiness, request ID propagation, manifest validation, readiness dashboard signal, Dockerfile policy checks, and bounded backfill runs. | Ran focused tests, Ruff, Pyright, dashboard/JSON validation, docs checks, and path-scoped whitespace checks. |
| 2026-04-29 | Created V5 tracker, then added dependency-readiness drill, post-deploy verification, roadmap consolidation, and queue-backed order events. | Ran Ruff, Pyright, focused pytest, Terraform fmt/validate, TFLint, Checkov, workflow/docs checks, and path-scoped whitespace checks. |
| 2026-04-29 | Consolidated `docs/ROADMAP.md`, `docs/ROADMAP_V2.md`, `docs/ROADMAP_V3.md`, `docs/ROADMAP_v4.md`, and `docs/ROADMAP_V5.md` into this file. | Ran roadmap reference search and path-scoped git diff whitespace checks. |

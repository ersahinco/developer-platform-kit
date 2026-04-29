# ECS DevOps Monorepo Roadmap V4

This file is the completed V4 cross-session tracker after the completed V1, V2,
and V3 passes. Active work continues in [docs/ROADMAP_V5.md](ROADMAP_V5.md).

## Current State

The repository already implements the high-value parts of
`.idea/architecture.md` that fit the current simple domain:

- Apps and packages monorepo shape with `apps/api`, `apps/backfill-worker`,
  `apps/data-export-job`, `packages/core`, and `packages/adapters`.
- Thin workload entry points around a shared domain and SQL adapter layer.
- Single-root Terraform stack with community AWS modules where they fit.
- GitHub Actions for app validation/deployment, infrastructure validation/plan,
  security scanning, CodeQL, Trivy image scanning, and manual AWS-changing
  workflows through OIDC.
- Complete safe database migration lifecycle with Liquibase, runtime read/write
  switches, bounded idempotent backfill, and contract-readiness checks.
- API liveness, database-backed readiness, request ID propagation, and
  Prometheus request metrics.
- Local and AWS data export flow with S3 raw and validated manifest
  conventions.
- Local Prometheus, Loki, and Grafana with readiness-failure visibility plus AWS
  CloudWatch alarms and runbooks.
- Ruff, Pyright, pytest, Terraform fmt, tflint, Checkov, pre-commit,
  Dependabot, docs link checks, shell syntax checks, GitHub workflow policy
  checks, Dockerfile policy checks, and dependency/secret audits.

V4 continues the architecture comparison without treating the reference tree as
a migration checklist. Keep the application domain small, but allow additional
workloads or extensions to existing applications when they demonstrate
production-grade SDLC, DevOps, infrastructure, data, observability, security, or
maintainability principles for well-established services at scale.

## Missing Implementation Review

| Architecture idea | Current decision | Why |
|---|---|---|
| `.editorconfig` baseline | Implemented in V4. | Small naming and formatting consistency gain with no dependency or runtime cost. |
| Extra apps such as consumer, scheduler, and admin | Conditional V4 candidates. | Add one only when it owns a real production workflow such as async processing, scheduled operations, or operator repair tasks. Prefer extending an existing app when that proves the same principle with less surface. |
| `packages/config`, `packages/telemetry`, and `packages/testing` | Deferred. | Existing config, metrics, and test fixtures are small enough in-place. Extract only when duplication appears. |
| `infra/modules`, `infra/stacks`, and `infra/catalogs` | Deferred. | The binding engineering principles prefer one Terraform root until real lifecycle boundaries exist. |
| `deploy/` task definition templates | Deferred. | ECS task definitions are Terraform-owned and rendered by CI from registered families; separate templates would duplicate ownership today. |
| `security/` policy tree | Deferred. | Security gates exist; exceptions and allowlists should appear only with real tracked policy. |
| Additional workflow validation tooling | Implemented in V4. | A dependency-free policy check now protects repo-specific workflow invariants without adding a general linter dependency. |

## Direction

V4 focuses on lean consistency and trust in the delivery system:

- Keep roadmap ownership current and unambiguous.
- Close small architecture gaps only when they reduce mistakes immediately.
- Prefer dependency-free or already-present tooling.
- Keep SDLC, DevOps, infra, data, observability, security, naming consistency,
  and lean maintainability ahead of domain expansion.
- Use the simple order/customer domain to demonstrate production patterns rather
  than adding business breadth.
- Allow a new workload when it proves a real operational pattern end to end:
  build, deploy, runtime config, data ownership, metrics, alarms, runbook,
  tests, and rollback.
- Avoid empty directories, speculative packages, internal Terraform modules, or
  extra runtime apps.

Each session should make one coherent improvement, verify it, update this file,
and preserve user-owned worktree changes.

## Candidate Production-Grade Slices

These are valid V4 directions when implemented as complete, verified slices.
Prefer the smallest slice that proves the principle from local development
through CI, infrastructure, observability, and operator documentation.

| Candidate | Preferred first shape | Production principle |
|---|---|---|
| API operational hardening | Extend `apps/api` with readiness semantics, request correlation, structured error responses, and focused tests. | Public services need diagnosable failures, stable contracts, and health signals that mean more than process liveness. |
| Async order event processing | Add a small SQS-backed consumer or extend the worker only after a real event flow exists. | Scaled services decouple request handling from background side effects with idempotency, DLQs, metrics, and replay guidance. |
| Scheduled maintenance workload | Extend `data-export-job` or add a scheduler only for a concrete maintenance/reporting task. | Recurring jobs need explicit ownership, idempotent outputs, freshness signals, and alarm-linked runbooks. |
| Operator/admin task surface | Add admin commands only for real migration, repair, or verification workflows. | Production systems need auditable one-off operations without exposing speculative app endpoints. |
| Data reliability refinement | Extend the export path with manifest validation, idempotent reruns, partition checks, or freshness tests. | Data jobs need recoverable outputs, explicit contracts, and observable success/failure states. |
| Observability maturity | Add focused metrics, dashboard panels, or alarms for a newly demonstrated runtime behavior. | Monitoring should follow real behavior and runbooks, not exist as dashboard decoration. |
| Security and supply-chain maturity | Add narrow checks or policies only when they protect an existing delivery path. | Shift-left controls should catch concrete mistakes without creating unused policy trees. |

## Phase Checklist

### Phase 1: Architecture Comparison

- [x] Compare the current repo against `.idea/architecture.md`.
- [x] Record missing implementation decisions in this tracker.
- [x] Keep deferred items explicit rather than silently absent.

### Phase 2: Naming and Formatting Consistency

- [x] Add the missing repo-level `.editorconfig` baseline.
- [x] Identify the next smallest consistency gap only after `.editorconfig` is verified.

### Phase 3: Lean Maintainability

- [x] Prefer checks or simplifications that protect existing workflows over new abstractions.
- [x] Avoid adding directories or policy files until there is real owned content.
- [x] Keep the application domain simple unless a platform workflow needs a concrete example.

### Phase 4: Production-Grade Runtime Patterns

- [x] Identify one existing workload that can be extended to show a production service principle before adding a new app.
- [x] Add request, background, or scheduled processing behavior only with tests, operational docs, and rollback notes.
- [x] Keep new runtime configuration minimal, documented, and safe by default.

### Phase 5: Async and Scheduled Workloads

- [x] Extend an existing background workload before adding a new consumer, scheduler, or admin app.
- [x] Include idempotency, pause/resume behavior, failure handling, structured logs, and operator documentation.
- [x] Avoid queue, event, or scheduler infrastructure unless local behavior and tests exist first.

### Phase 6: Data and Observability at Scale

- [x] Strengthen the data export contract with rerun safety, manifest validation, or partition/freshness checks.
- [x] Add observability only for real service behavior, with a dashboard or alarm tied to an operator action.
- [x] Keep CloudWatch and local Prometheus/Grafana documentation aligned when new signals are added.

### Phase 7: Security and Delivery Confidence

- [x] Prefer narrow policy checks that protect existing workflows over broad unused policy trees.
- [x] Keep GitHub OIDC, manual cloud-changing confirmations, image scanning, dependency auditing, and secret scanning aligned as workflows evolve.
- [x] Add exceptions or allowlists only when there is a real exception to track.

## Next Session Should Start Here

1. Read `docs/ROADMAP_V5.md` first, then this file, `docs/ROADMAP_V3.md`,
   `docs/ROADMAP_V2.md`, `README.md`, `docs/architecture.md`,
   `.idea/architecture.md`, and `.kiro/steering/engineering-principles.md`.
2. Check `git status --short` before editing. The `.gitignore` file may contain
   user-owned changes.
3. Pick exactly one unchecked V4 item or one newly discovered smallest
   high-value SDLC/DevOps/infra/data/observability/security/naming consistency
   step.
4. Make the smallest coherent change, verify it, update this file, and commit.

Recommended next pick: continue from `docs/ROADMAP_V5.md`. V4 is complete; keep
this file as history unless a V4 correction is needed.

## Documentation Ownership

- `README.md` is the short project index.
- `docs/ROADMAP.md` is the completed V1 history.
- `docs/ROADMAP_V2.md` is the completed V2 history.
- `docs/ROADMAP_V3.md` is the completed V3 history.
- `docs/ROADMAP_v4.md` is the completed V4 history.
- `docs/ROADMAP_V5.md` is the current progress tracker.
- `docs/deployment.md` is the detailed AWS operator runbook.
- `docs/architecture.md` keeps long-form rationale and intentionally omitted
  hardening work.
- New `ops/` or `security/` files should appear only with concrete owned content.

## Decisions and Assumptions

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-29 | Track active post-V3 work in `docs/ROADMAP_v4.md`. | The user requested this exact tracker path for cross-session progress. |
| 2026-04-29 | Add `.editorconfig` before larger architecture tree changes. | It implements a missing baseline from `.idea/architecture.md` without adding dependencies, runtime surface, or speculative folders. |
| 2026-04-29 | Add a dependency-free GitHub workflow policy check instead of a general workflow linter. | The repo needs two concrete invariants protected locally and in CI; a broad linter would add dependency and maintenance surface. |
| 2026-04-29 | Allow additional workloads or extensions when they demonstrate a complete production-grade pattern. | The goal is not placeholder breadth; it is realistic service operation at scale around a simple domain. |
| 2026-04-29 | Extend the existing API before adding a new workload for the first runtime-pattern slice. | Liveness, readiness, and request correlation are production service basics and fit the current API with no new infrastructure or dependency surface. |
| 2026-04-29 | Strengthen the existing data export manifest before adding a larger data platform. | Raw byte counts and SHA-256 checksums make the current S3 contract verifiable without adding Glue, Athena, or orchestration complexity. |
| 2026-04-29 | Surface API readiness failures in the local Grafana dashboard before adding new monitoring infrastructure. | `/ready` already exposes dependency health and Prometheus already records route/status metrics, so the dashboard can make the signal actionable without new runtime code. |
| 2026-04-29 | Add a narrow Dockerfile policy check instead of a broad container policy tree. | The repo already uses Trivy for CVEs; the local check protects repository-owned invariants such as non-`latest` bases, multi-stage app builds, and non-root runtime users. |
| 2026-04-29 | Extend the existing backfill worker with bounded runs instead of adding a new consumer. | The current worker already owns a real background repair workflow; `BACKFILL_MAX_BATCHES` adds operator-controlled throttling while preserving checkpointed idempotency. |
| 2026-04-29 | Continue deferring packages, Terraform splits, `deploy/`, and `security/` trees until they have concrete ownership. | The current value is complete SDLC and operator reliability around a simple domain, not breadth of placeholders. |

## Completed Work Log

| Date | Work | Verification |
|---|---|---|
| 2026-04-29 | Created the V4 tracker, recorded the architecture comparison decisions, repointed the README/current roadmap references, and added the missing `.editorconfig` baseline. | Ran documentation link checks, Markdown whitespace checks, and git diff review. |
| 2026-04-29 | Added a dependency-free GitHub workflow policy check for path-filter self-coverage and OIDC workflow confirmation gates, wired it into Make, pre-commit, and the Security workflow, and documented the repo-specific scope. | Ran the workflow checker, focused Ruff, focused workflow-policy tests, documentation link checks, and path-scoped git diff whitespace checks. |
| 2026-04-29 | Expanded V4 to include production-grade workload and application-extension candidates while preserving the one-slice, simple-domain guardrails. | Documentation-only change; ran documentation link checks and path-scoped git diff whitespace checks. |
| 2026-04-29 | Extended the API with database-backed `/ready` readiness and `X-Request-ID` propagation while keeping `/health` as lightweight liveness. | Ran focused API tests, Ruff, Pyright, documentation link checks, and path-scoped git diff whitespace checks. |
| 2026-04-29 | Strengthened the data export manifest with raw byte count and SHA-256 validation before manifest upload or success logging. | Ran focused data export tests, Ruff, Pyright, documentation link checks, and path-scoped git diff whitespace checks. |
| 2026-04-29 | Added a local Grafana readiness-failure stat for `/ready` 5xx responses and documented the operator path to existing app/RDS runbooks. | Ran the dashboard contract test, Ruff, documentation link checks, JSON parsing, and path-scoped git diff whitespace checks. |
| 2026-04-29 | Added a dependency-free Dockerfile policy check for non-`latest` base images, multi-stage app builds, and non-root runtime users, wired into Make, pre-commit, and the Security workflow. | Ran the Dockerfile checker, focused policy tests, Ruff, Pyright, documentation link checks, and path-scoped git diff whitespace checks. |
| 2026-04-29 | Added `BACKFILL_MAX_BATCHES` so the checkpointed backfill worker can pause after a bounded number of committed batches for throttled repair or replay. | Ran focused backfill tests, Ruff, Pyright, documentation link checks, and path-scoped git diff whitespace checks. |

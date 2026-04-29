# ECS DevOps Monorepo Roadmap V5

This file is the active cross-session tracker after the completed V1, V2, V3,
and V4 passes. V5 should focus on bigger production-readiness themes while
keeping the simple order/customer domain and the single-stack operating model.

## Current State

The repository now has a complete lean SDLC baseline:

- FastAPI API with `/health`, `/ready`, request ID propagation, and Prometheus
  request metrics.
- Checkpointed backfill worker with bounded pause/resume runs for throttled
  repair or replay.
- Scheduled data export job with raw CSV output, validated manifests, and S3
  data hub publishing.
- Single-root Terraform stack for ECS, RDS, ALB, ECR, S3 data hub, EventBridge,
  CloudWatch alarms, and GitHub OIDC.
- Local Prometheus, Loki, and Grafana with readiness-failure visibility.
- Runbooks for deployment rollback, app health, app edge symptoms, RDS pressure,
  and data export failures.
- Local and CI checks for Ruff, Pyright, pytest, Terraform, Checkov, TFLint,
  CodeQL, Trivy, dependency audit, secret scan, workflow policy, Dockerfile
  policy, docs links, and shell syntax.

V5 should not add empty architecture folders or speculative platform splits.
Every slice should prove one production operator story end to end.

## Direction

V5 focuses on four larger themes:

- Production incident drills: rehearse concrete failures using existing alarms,
  runbooks, logs, metrics, and recovery commands.
- Rollout verification: make deployment and migration progress observable and
  mechanically checkable before, during, and after a rollout.
- Async event processing with a real queue: add queue-backed behavior only when
  there is a concrete order workflow, idempotency model, DLQ path, metrics,
  alarms, and runbook.
- Documentation consolidation: reduce duplicated roadmap/runbook knowledge and
  make the operator path easier to follow.

Each session should make one coherent improvement, verify it, update this file,
and commit. Preserve user-owned worktree changes.

## Candidate V5 Slices

| Candidate | Preferred first shape | Why |
|---|---|---|
| Incident drill: app dependency readiness | Add a documented local/AWS drill that simulates database-readiness failure and maps symptoms to Grafana, CloudWatch, and runbooks. | Proves the new `/ready` and readiness dashboard are operationally useful. |
| Incident drill: data export failure | Add a drill for failed raw upload or missing success manifest, including expected alarm/runbook path. | Exercises the existing data export failure alarm and validated manifest contract. |
| Rollout preflight verification | Add or extend a script that checks app readiness, runtime config, migration phase, current ECS task family names, and data export health before advancing rollout. | Reduces operator guesswork during the safe migration lifecycle. |
| Rollout post-deploy verification | Add a focused smoke script or Make target that checks `/ready`, `/metrics`, read/write mode, and the expected task/image metadata after deploy. | Closes the loop between CI deploy and operator confidence. |
| Queue-backed order event v1 | Add one SQS-backed order event workflow only after defining the event, idempotency key, DLQ behavior, local test path, Terraform resources, metrics, and runbook. | Demonstrates real async processing without building a placeholder consumer. |
| Documentation consolidation | Summarize V1-V4 accomplishments, move repeated next-session instructions into one place, and keep README as the short index. | Makes the repo easier for a fresh engineer or agent to operate. |

## Phase Checklist

### Phase 1: V5 Planning Foundation

- [x] Create `docs/ROADMAP_V5.md`.
- [x] Repoint README and V4 current-roadmap references to V5.
- [x] Keep V1-V4 as history and avoid rewriting completed trackers except for
  transition notes.

### Phase 2: Production Incident Drills

- [x] Add one concrete incident drill for an existing signal.
- [x] Include trigger, expected symptoms, investigation commands, recovery, and
  success criteria.
- [x] Link the drill from the relevant runbook or docs entrypoint.

### Phase 3: Rollout Verification

- [x] Add one preflight or post-deploy verification improvement.
- [x] Keep it runnable locally or in CI without broad new dependencies.
- [x] Document where it fits in the migration/deploy sequence.

### Phase 4: Async Event Processing

- [ ] Add queue-backed async behavior only with a real event and idempotency
  contract.
- [ ] Include DLQ/failure handling, metrics or logs, tests, and a runbook.
- [ ] Avoid adding a consumer app until the local behavior and infrastructure
  contract are both justified.

### Phase 5: Documentation Consolidation

- [x] Consolidate repeated roadmap guidance after the first V5 implementation
  slice lands.
- [x] Keep README short and index-like.
- [x] Keep `docs/architecture.md` focused on rationale and intentionally omitted
  hardening work.

## Next Session Should Start Here

1. Read [docs/roadmaps.md](roadmaps.md), then this file.
2. Check `git status --short` before editing. The `.gitignore` file may contain
   user-owned changes.
3. Pick one coherent unchecked V5 item or newly discovered high-value operator
   slice.
4. Make the smallest complete change, verify it, update this file, and commit.

Recommended next pick: start Phase 4 only with a concrete queue-backed order
event, idempotency contract, DLQ path, metrics or logs, tests, and a runbook.

## Documentation Ownership

See [docs/roadmaps.md](roadmaps.md) for the shared roadmap index, continuation
rules, and documentation ownership map.

## Decisions and Assumptions

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-29 | Track active post-V4 work in `docs/ROADMAP_V5.md`. | V4 completed its architecture comparison and production-grade slice checklist; V5 needs a larger incident, rollout, async, and docs-consolidation focus. |
| 2026-04-29 | Keep the domain simple during V5. | The value is in production operating practices, not expanding business features. |
| 2026-04-29 | Prefer drills and verification before adding new queue infrastructure. | Existing signals and runbooks should prove useful before the repo takes on more runtime surface. |

## Completed Work Log

| Date | Work | Verification |
|---|---|---|
| 2026-04-29 | Added a roadmap index and continuation guide, trimmed repeated README roadmap guidance, and moved V5 session guidance to the shared roadmap page. | Ran Markdown link checks and path-scoped git diff whitespace checks. |
| 2026-04-29 | Added read-only runtime mode endpoints and a post-deploy verifier that checks `/health`, `/ready`, `/metrics`, runtime modes, and optional ECS task/image metadata; wired it into the deploy workflow and Makefile. | Ran Ruff, Pyright, workflow policy checks, Markdown link checks, focused pytest coverage, and path-scoped git diff whitespace checks. |
| 2026-04-29 | Added an app dependency-readiness incident drill that stops local PgBouncer, confirms `/health` stays live while `/ready` fails, maps symptoms to Prometheus/Grafana/Loki and AWS runbooks, and linked it from observability and app-health docs. | Ran Markdown link checks and path-scoped git diff whitespace checks. |
| 2026-04-29 | Created the V5 tracker with production incident drills, rollout verification, async queue processing, and documentation consolidation as the main themes; repointed README and V4 current-roadmap references to V5. | Documentation-only change; ran documentation link checks and path-scoped git diff whitespace checks. |

# ECS DevOps Monorepo Roadmap V4

This file is the active cross-session tracker after the completed V1, V2, and
V3 passes. Start here before changing SDLC, DevOps, infrastructure, data,
observability, security, naming, or operator workflows.

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
  switches, backfill, and contract-readiness checks.
- Local and AWS data export flow with S3 raw and manifest conventions.
- Local Prometheus, Loki, and Grafana plus AWS CloudWatch alarms and runbooks.
- Ruff, Pyright, pytest, Terraform fmt, tflint, Checkov, pre-commit,
  Dependabot, docs link checks, shell syntax checks, GitHub workflow policy
  checks, and dependency/secret audits.

V4 continues the architecture comparison without treating the reference tree as
a migration checklist. Keep the application domain small and prefer complete
operator workflows over new folders, apps, modules, or abstractions.

## Missing Implementation Review

| Architecture idea | Current decision | Why |
|---|---|---|
| `.editorconfig` baseline | Implemented in V4. | Small naming and formatting consistency gain with no dependency or runtime cost. |
| Extra apps such as consumer, scheduler, and admin | Deferred. | No current domain workflow needs them; adding placeholders would violate lean development. |
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
- Keep SDLC, DevOps, infra, data, observability, and naming consistency ahead of
  domain expansion.
- Avoid empty directories, speculative packages, internal Terraform modules, or
  extra runtime apps.

Each session should make one coherent improvement, verify it, update this file,
and preserve user-owned worktree changes.

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

## Next Session Should Start Here

1. Read this file first, then `docs/ROADMAP_V3.md`, `docs/ROADMAP_V2.md`,
   `README.md`, `docs/architecture.md`, `.idea/architecture.md`, and
   `.kiro/steering/engineering-principles.md`.
2. Check `git status --short` before editing. The `.gitignore` file may contain
   user-owned changes.
3. Pick exactly one unchecked V4 item or one newly discovered smallest
   high-value SDLC/DevOps/infra/data/observability/naming consistency step.
4. Make the smallest coherent change, verify it, update this file, and commit.

Recommended next pick: review the pending `.gitignore` consistency cleanup as a
separate slice, but first confirm it is intentional user-owned work and fix the
trailing whitespace before staging it.

## Documentation Ownership

- `README.md` is the short project index.
- `docs/ROADMAP.md` is the completed V1 history.
- `docs/ROADMAP_V2.md` is the completed V2 history.
- `docs/ROADMAP_V3.md` is the completed V3 history.
- `docs/ROADMAP_v4.md` is the current progress tracker.
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
| 2026-04-29 | Continue deferring extra apps, packages, Terraform splits, `deploy/`, and `security/` trees. | The current value is complete SDLC and operator reliability around a simple domain, not breadth of placeholders. |

## Completed Work Log

| Date | Work | Verification |
|---|---|---|
| 2026-04-29 | Created the V4 tracker, recorded the architecture comparison decisions, repointed the README/current roadmap references, and added the missing `.editorconfig` baseline. | Ran documentation link checks, Markdown whitespace checks, and git diff review. |
| 2026-04-29 | Added a dependency-free GitHub workflow policy check for path-filter self-coverage and OIDC workflow confirmation gates, wired it into Make, pre-commit, and the Security workflow, and documented the repo-specific scope. | Ran the workflow checker, focused Ruff, focused workflow-policy tests, documentation link checks, and path-scoped git diff whitespace checks. |

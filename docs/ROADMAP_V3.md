# ECS DevOps Monorepo Roadmap V3

This file is the completed V3 progress tracker after the completed V1 and V2
passes. Active work continues in [docs/ROADMAP_V5.md](ROADMAP_V5.md); V4 is
preserved in [docs/ROADMAP_v4.md](ROADMAP_v4.md).

## Current State

The repository is a lean AWS delivery sandbox with a complete operator-quality
baseline:

- One FastAPI app, one backfill worker, and one scheduled data export job.
- Shared domain contracts in `packages/core` and SQLAlchemy/Postgres adapters in
  `packages/adapters`.
- Liquibase expand, dual-write, backfill, switch, and contract flow.
- Terraform-managed ECS, RDS, ALB, ECR, GitHub OIDC, S3 data hub, EventBridge
  schedule, CloudWatch alarms, and runbook-linked operational signals.
- GitHub Actions for app validation/deployment, infrastructure validation/plan,
  security scanning, dependency audit, CodeQL, Trivy image scanning, and manual
  AWS-changing workflows.
- Local Prometheus, Loki, and Grafana observability profile.
- Ruff, Pyright, pytest, Terraform fmt, tflint, Checkov, pre-commit, and
  Dependabot in the quality and maintenance path.

V3 should continue comparing the implementation against `.idea/architecture.md`
without treating that file as a migration checklist. Keep the application domain
simple and favor small improvements that make the existing SDLC easier to trust.

## Direction

V3 focuses on lean delivery-system maturity:

- Complete and aligned local, pre-commit, and CI quality gates.
- Small DevOps checks that protect scripts, workflows, and operator commands.
- Naming and documentation consistency where it reduces future mistakes.
- Infrastructure and observability refinements only when they close a real gap.
- No speculative app workloads, empty folders, internal Terraform modules, or
  platform splits.

Each session should make one coherent improvement, verify it, update this file,
and preserve user-owned worktree changes.

## Phase Checklist

### Phase 1: Quality Gate Completeness

- [x] Add a zero-dependency shell syntax gate for deployment and operator scripts.
- [x] Identify the next smallest local/CI/pre-commit alignment gap after shell syntax checks.

### Phase 2: Naming and Documentation Consistency

- [x] Keep roadmap ownership clear now that V3 is active.
- [x] Remove stale references to completed trackers when they could mislead future sessions.
- [x] Keep `README.md` short and index-like.

### Phase 3: Lean Maintainability

- [x] Prefer checks or simplifications that protect existing workflows over new abstractions.
- [x] Avoid adding directories or policy files until there is real owned content.
- [x] Keep `.idea/architecture.md` as inspiration, not a one-shot migration map.

## Next Session Should Start Here

1. Read `docs/ROADMAP_V5.md` first, then `docs/ROADMAP_v4.md`, this file,
   `docs/ROADMAP_V2.md`, `README.md`, `docs/architecture.md`, and
   `.kiro/steering/engineering-principles.md`.
2. Check `git status --short` before editing. The `.gitignore` file may contain
   user-owned changes.
3. Compare the current repo against `.idea/architecture.md`.
4. Pick exactly one unchecked V3 item or one newly discovered smallest
   high-value SDLC/DevOps/infra/data/observability/naming consistency step.
5. Make the smallest coherent change, verify it, update the active roadmap, and commit.

Recommended next pick: continue from `docs/ROADMAP_V5.md`. V3 is complete; keep
this file as history unless a V3 correction is needed.

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
| 2026-04-29 | Track active post-V2 work in `docs/ROADMAP_V3.md`. | V2 is complete, and the uppercase V3 suffix matches `docs/ROADMAP_V2.md` and the current user-facing roadmap reference. |
| 2026-04-29 | Keep V3 focused on delivery-system maturity rather than new app domain features. | The current interview value is in complete SDLC, DevOps, infra, data, observability, naming consistency, and lean maintainability. |
| 2026-04-29 | Prefer zero-dependency checks when they catch real operator mistakes. | Small built-in gates reduce CI and local risk without adding maintenance overhead. |

## Completed Work Log

| Date | Work | Verification |
|---|---|---|
| 2026-04-29 | Added a zero-dependency shell syntax gate for deployment and operator scripts in Make, pre-commit, and the App workflow. | Ran `bash -n scripts/*.sh`, `make lint-scripts`, workflow/pre-commit YAML parsing, and documentation whitespace checks. |
| 2026-04-29 | Renamed the active tracker to `docs/ROADMAP_V3.md` and updated roadmap references for version-suffix consistency. | Ran roadmap reference search and documentation whitespace checks. |
| 2026-04-29 | Completed the remaining V3 checklist with a dependency-free local Markdown link checker wired into Make, pre-commit, and CI. | Ran the docs link checker through direct, Make, and pre-commit paths; ran Ruff on the new script, YAML parsing for changed workflow/config files, and documentation whitespace checks. |

# ECS DevOps Monorepo Roadmap V2

This file is the completed V2 progress tracker. V1 is preserved in
`docs/ROADMAP.md` as project history, and active work continues in
`docs/ROADMAP_V5.md`.

## Current State

The repository has completed the first architecture pass:

- One single-stack AWS delivery sandbox.
- One FastAPI app in `apps/api/`.
- One backfill worker in `apps/backfill-worker/`.
- One scheduled ECS data export job in `apps/data-export-job/`.
- Pure domain contracts in `packages/core/`.
- SQLAlchemy/Postgres implementations in `packages/adapters/`.
- Liquibase expand, dual-write, backfill, switch, and contract flow.
- Terraform-managed ECS, RDS, ALB, ECR, GitHub OIDC, S3 data hub, and EventBridge schedule.
- GitHub Actions for app validation/deployment and Terraform validation/plan/apply.
- Local Prometheus, Loki, and Grafana observability profile.
- Ruff, Pyright, pytest, Terraform fmt, tflint, Checkov, Trivy, and Docker image builds in the delivery path.

V2 should improve operational maturity without expanding the application domain.

## Direction

V2 focuses on lean operator quality:

- AWS-native operational signals.
- Runbooks tied to real alarms or manual workflows.
- Shift-left security checks.
- Dependency and image maintenance.
- Quality gate alignment.
- Data job operability.
- Documentation hygiene.

Each session should make one coherent improvement, verify it, and update this
file.

## Do Not Pursue Yet

The following are intentionally out of scope for V2 unless this file is updated
with a new decision:

- Multi-account AWS orgs, hub/spoke Transit Gateway, or network/security/platform/data/workload Terraform stack splits.
- Internal Terraform modules such as `ecs-workload` or `ecs-scheduled-task`; continue using existing community modules where they fit.
- Extra application workloads such as consumer, scheduler, or admin apps.
- Kafka, Glue, Athena, Lake Formation, or broader data platform services.
- Deep domain-module restructuring under `packages/core`.

Do not create empty `ops/`, `security/`, or other placeholder directories. Add
them only with real owned content.

## Phase Checklist

### Phase 1: AWS-Native Operational Signals

- [x] Add the first CloudWatch alarm for scheduled data export task failure.
- [x] Add ECS service health alarms.
- [x] Add ALB 5xx and latency alarms.
- [x] Add RDS CPU, storage, and connection pressure alarms.
- [x] Keep each alarm slice paired with a concrete verification command and, when useful, a runbook.

### Phase 2: Runbooks and Incident Response

- [x] Add `ops/runbooks/` with the first real runbook, not as an empty folder.
- [x] Write scheduled data export failure triage and recovery runbook.
- [x] Write ECS deploy rollback runbook if existing deployment docs are not enough for alarm response.
- [x] Link runbooks from the alarm or workflow they support.

### Phase 3: Shift-Left Security

- [x] Add one lightweight secret scanning gate.
- [x] Add one Python dependency scanning gate.
- [x] Add one SAST gate, preferably GitHub-native or low-maintenance.
- [x] Add SBOM generation only when it has a clear consumer in CI or docs.
- [x] Add `security/exceptions.yaml` only when security exceptions become tracked policy.

### Phase 4: Dependency and Image Maintenance

- [x] Add automated dependency update policy for Python dependencies.
- [x] Add automated update policy for GitHub Actions.
- [x] Keep Trivy before image push and ECR scan-on-push.
- [x] Avoid base image digest pinning unless automated digest renewal is added in the same slice.

### Phase 5: Quality Gate Alignment

- [x] Align `.pre-commit-config.yaml`, `make lint`, and CI around Ruff, Pyright, Terraform fmt, and lightweight checks.
- [x] Keep slow checks out of default local hooks unless they prevent concrete bugs.
- [x] Document any intentional difference between pre-commit, local Make targets, and CI.

### Phase 6: Data Job Operability

- [x] Add operational signal for data export success or failure.
- [x] Add data freshness signal after export failure alarm exists.
- [x] Keep raw and manifest S3 conventions stable.
- [x] Do not add Glue, Athena, Kafka, Lake Formation, or larger data platform resources.

### Phase 7: Documentation Hygiene

- [x] Keep `README.md` short and index-like.
- [x] Keep long-form procedures in `docs/`.
- [x] Add new docs files only when there is real content and a clear owner.
- [x] Keep this V2 roadmap updated after each completed slice.

## Next Session Should Start Here

1. Read `docs/ROADMAP_V5.md` first, then `docs/ROADMAP_v4.md`,
   `docs/ROADMAP_V3.md`, this file, `README.md`, `docs/architecture.md`, and
   `.kiro/steering/engineering-principles.md`.
2. Check `git status --short` before editing. The `.gitignore` file may contain user-owned changes.
3. Pick exactly one unchecked V3 item or one newly discovered smallest high-value step.
4. Make the smallest change that advances that item.
5. Run the relevant verification.
6. Update the active roadmap before ending the session.

Recommended next pick: continue from `docs/ROADMAP_V5.md`. V2 is complete; keep
this file as history unless a V2 correction is needed.

Previous transition note: V2 is complete. Start the next session by comparing
the current repo against `.idea/architecture.md`, preserving the V2 guardrails,
and creating a new tracker only if there is a clear next operator-maturity
theme.

## Documentation Ownership

- `README.md` is the short project index.
- `docs/ROADMAP.md` is the completed V1 history.
- `docs/ROADMAP_V2.md` is the completed V2 history.
- `docs/ROADMAP_V3.md` is the completed V3 history.
- `docs/ROADMAP_v4.md` is the completed V4 history.
- `docs/ROADMAP_V5.md` is the current progress tracker.
- `docs/deployment.md` is the detailed AWS operator runbook.
- `docs/architecture.md` keeps long-form rationale and intentionally omitted hardening work.
- New `ops/` or `security/` files should appear only with concrete owned content.

## Decisions and Assumptions

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-29 | Keep V1 in `docs/ROADMAP.md` and track new work in `docs/ROADMAP_V2.md`. | V1 is complete enough to preserve as history, while V2 needs a current, smaller operator-quality focus. |
| 2026-04-29 | Keep the repo single-stack and community-module-first in V2. | The existing Terraform root is working; stack splits and internal modules would add lifecycle complexity before there is repeated infrastructure shape. |
| 2026-04-29 | Keep the application domain simple during V2. | The remaining value is in DevOps, infra, data operability, security, observability, and maintainability. |
| 2026-04-29 | Add folders such as `ops/` and `security/` only with real content. | Empty placeholders are speculative complexity and make ownership less clear. |

## Completed Work Log

| Date | Work | Verification |
|---|---|---|
| 2026-04-29 | Created the V2 roadmap tracker and linked it from V1 and the README. | Documentation-only change; checked links and whitespace. |
| 2026-04-29 | Added the first AWS-native operational signal: a CloudWatch alarm for EventBridge Scheduler data export target delivery failures, plus a matching runbook. | Ran `terraform fmt -check -recursive infra/`, `terraform -chdir=infra validate`, Checkov, and documentation whitespace checks. |
| 2026-04-29 | Added an ALB target health alarm for the app service and a matching unhealthy-service runbook. | Ran `terraform fmt -check -recursive infra/`, `terraform -chdir=infra validate`, `tflint --format compact`, Checkov, and documentation whitespace checks. |
| 2026-04-29 | Added ALB target 5xx and p95 latency alarms for app edge symptoms, plus a shared runbook. | Ran `terraform fmt -check -recursive infra/`, `terraform -chdir=infra validate`, `tflint --format compact`, Checkov, and documentation whitespace checks. |
| 2026-04-29 | Added RDS CPU, free storage, and connection pressure alarms, plus a shared RDS pressure runbook. | Ran `terraform fmt -check -recursive infra/`, `terraform -chdir=infra validate`, `tflint --format compact`, Checkov, and documentation whitespace checks. |
| 2026-04-29 | Added a focused ECS deploy rollback runbook and linked app alarm runbooks to it. | Documentation-only change; ran `git diff --check` on the edited docs. |
| 2026-04-29 | Added a dependency-free high-confidence secret scan gate with local Make, CI, and unit-test coverage. | Ran secret scan, focused scanner tests, Ruff, Pyright, full pytest, and documentation whitespace checks. |
| 2026-04-29 | Added a Python dependency audit gate using `pip-audit` against a frozen `uv.lock` export, and bumped `pytest` to clear the initial vulnerability finding. | Ran `uv lock`, dependency audit, secret scan, focused audit tests, Ruff, Pyright, full pytest, and documentation whitespace checks. |
| 2026-04-29 | Added GitHub CodeQL as the low-maintenance Python SAST gate. | Documentation/workflow-only change; parsed the workflow YAML and ran documentation whitespace checks. |
| 2026-04-29 | Documented that SBOM generation and `security/exceptions.yaml` stay deferred until they have real consumers or tracked policy. | Documentation-only change; ran documentation whitespace checks. |
| 2026-04-29 | Added weekly Dependabot `uv` updates for Python dependencies. | Parsed the Dependabot YAML and ran documentation whitespace checks. |
| 2026-04-29 | Added weekly Dependabot updates for GitHub Actions. | Parsed the Dependabot YAML and ran documentation whitespace checks. |
| 2026-04-29 | Confirmed ECR scan-on-push and made the mirrored PgBouncer image follow the same Trivy-before-push policy as first-party images. | Parsed the app workflow YAML and ran documentation whitespace checks. |
| 2026-04-29 | Documented the Phase 4 decision to defer base image digest pinning until automated digest renewal exists. | Documentation-only change; ran documentation whitespace checks. |
| 2026-04-29 | Aligned quality gates by adding pre-commit hooks for the local secret scan and Pyright, while documenting slower checks that stay in Make and CI. | Ran the new pre-commit hooks, Ruff, Pyright, secret scan, and documentation whitespace checks. |
| 2026-04-29 | Added a CloudWatch Logs metric filter that counts successful scheduled data export manifests as a custom `SuccessCount` metric. | Ran Terraform fmt, validate, tflint, Checkov, and documentation whitespace checks. |
| 2026-04-29 | Added a data export freshness alarm that fires when no successful export is observed for two daily evaluation windows. | Ran Terraform fmt, validate, tflint, Checkov, and documentation whitespace checks. |
| 2026-04-29 | Confirmed the raw and manifest S3 key convention remains stable and kept larger data platform services deferred. | Documentation-only change; ran documentation whitespace checks. |
| 2026-04-29 | Completed the V2 documentation hygiene pass: README remains index-like, long procedures stay in `docs/` or concrete runbooks, and the roadmap is current. | Ran document size/placeholder checks and documentation whitespace checks. |

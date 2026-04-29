# ECS DevOps Monorepo Roadmap V2

This file is the active post-V1 progress tracker. V1 is preserved in
`docs/ROADMAP.md` as project history. Start here before changing observability,
security, dependency maintenance, runbooks, or operator workflows.

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
- [ ] Add ALB 5xx and latency alarms.
- [ ] Add RDS CPU, storage, and connection pressure alarms.
- [ ] Keep each alarm slice paired with a concrete verification command and, when useful, a runbook.

### Phase 2: Runbooks and Incident Response

- [x] Add `ops/runbooks/` with the first real runbook, not as an empty folder.
- [x] Write scheduled data export failure triage and recovery runbook.
- [ ] Write ECS deploy rollback runbook if existing deployment docs are not enough for alarm response.
- [x] Link runbooks from the alarm or workflow they support.

### Phase 3: Shift-Left Security

- [ ] Add one lightweight secret scanning gate.
- [ ] Add one Python dependency scanning gate.
- [ ] Add one SAST gate, preferably GitHub-native or low-maintenance.
- [ ] Add SBOM generation only when it has a clear consumer in CI or docs.
- [ ] Add `security/exceptions.yaml` only when security exceptions become tracked policy.

### Phase 4: Dependency and Image Maintenance

- [ ] Add automated dependency update policy for Python dependencies.
- [ ] Add automated update policy for GitHub Actions.
- [ ] Keep Trivy before image push and ECR scan-on-push.
- [ ] Avoid base image digest pinning unless automated digest renewal is added in the same slice.

### Phase 5: Quality Gate Alignment

- [ ] Align `.pre-commit-config.yaml`, `make lint`, and CI around Ruff, Pyright, Terraform fmt, and lightweight checks.
- [ ] Keep slow checks out of default local hooks unless they prevent concrete bugs.
- [ ] Document any intentional difference between pre-commit, local Make targets, and CI.

### Phase 6: Data Job Operability

- [ ] Add operational signal for data export success or failure.
- [ ] Add data freshness signal after export failure alarm exists.
- [ ] Keep raw and manifest S3 conventions stable.
- [ ] Do not add Glue, Athena, Kafka, Lake Formation, or larger data platform resources.

### Phase 7: Documentation Hygiene

- [ ] Keep `README.md` short and index-like.
- [ ] Keep long-form procedures in `docs/`.
- [ ] Add new docs files only when there is real content and a clear owner.
- [ ] Keep this V2 roadmap updated after each completed slice.

## Next Session Should Start Here

1. Read this file first, then `README.md`, `docs/architecture.md`, and `.kiro/steering/engineering-principles.md`.
2. Check `git status --short` before editing. The `.gitignore` file may contain user-owned changes.
3. Pick exactly one unchecked V2 item.
4. Make the smallest change that advances that item.
5. Run the relevant verification.
6. Update this file before ending the session.

Recommended next pick: add a CloudWatch alarm for scheduled data export task
failure and a matching runbook. Keep it to one alarm plus one real runbook.

## Documentation Ownership

- `README.md` is the short project index.
- `docs/ROADMAP.md` is the completed V1 history.
- `docs/ROADMAP_V2.md` is the current progress tracker.
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

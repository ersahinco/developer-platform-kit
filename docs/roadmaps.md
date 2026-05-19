# Roadmap

This is the continuation tracker. It records current, next, waiting, and done
work only. Durable project shape belongs in canonical docs:

- [Ubiquitous Language](ubiquitous-language.md) defines shared terms for humans
  and code generation.
- [Architecture](architecture.md) explains the current system.
- [Platform Contract](platform-contract.md), [Runtime Toolkit](runtime-toolkit.md),
  and `platform/workloads.json` define portable workload/runtime expectations,
  portability status, and intentional provider dependencies.

## Current Focus

| Area | State | Notes |
|---|---|---|
| Delivery toolkit | Current | Keep workflows metadata-driven and review-gated, and prefer pragmatic pytest/runtime checks over bespoke validation layers. |
| Observability | Current | Keep the local Prometheus/Loki/Tempo/Grafana baseline under `platform/concerns/observability` and the AWS ADOT sidecar; CloudWatch remains the AWS rollback and managed-resource signal plane. |
| Portability | Current | Keep provider dependencies at runtime/delivery edges; app code and contracts stay provider-neutral. |
| Data and database | Current | Keep PostgreSQL semantics, Liquibase, PgBouncer expectations, data export manifests, and provider SDK isolation explicit. |
| Repo model | Current | Keep the platform monorepo seed explicit: infra catalog, platform concerns, and workload examples. |
| Capability map | Current | Keep `docs/platform-capabilities.md` aligned with the real platform surface; add capabilities only for real workload need. |

## Next

| Area | Work | Trigger |
|---|---|---|
| Build and containerize | Keep runtime conformance and image/security gates fast as workloads grow. | Do this with the next real workload, not synthetic scaffolding. |
| Workload onboarding | Keep `docs/adding-workloads.md` aligned with the real workload contract and smallest supported runtime patterns. | Update it when the next workload introduces a genuinely new shape. |
| Runtime portability | Add a second runtime target only for a concrete cost, reliability, or capability benefit. | The capability contract is ready; a demo-only runtime would add noise. |
| Dapr scope | Keep pub/sub as the standard app-facing transport boundary and expand only when a workload needs more platform capability. | Standardization is useful here; avoid speculative building blocks. |
| Release evidence | Turn on CI-to-Loki publishing when there is a private or authenticated runner path. | Artifacts already exist; network/security path is the missing piece. |

## Waiting

| Decision | Why |
|---|---|
| Broader Dapr platform scope | The next slice should clarify a real boundary, not add a platform layer for its own sake. |
| Data analytics stack | DuckDB, dbt, dlt, and orchestration stay deferred until the app/infra roadmap asks for analytics work. |
| CloudWatch reduction | AWS-native alarms still protect rollbacks and freshness; reduce only after a deliberate metrics/ruler path exists. |

## Done

| Work | Result |
|---|---|
| Clean Architecture package shape | `apps/*` reference hosts with `packages/domain`, `packages/application`, and `packages/infrastructure`. |
| Terraform split | `infra/platform` owns bootstrap/network/OIDC; `infra/app` owns runtime resources. |
| Local development housekeeping | Devcontainer-first workflow, root `compose.yaml`, and shared `platform/concerns/observability/` assets. |
| ECS-hosted LGTM retirement | Cloud keeps CloudWatch logs, ALB access logs, and ADOT sidecar telemetry; OSS LGTM stays local/external. |
| Workflow bloat reduction | App image builds come from workload metadata; deploy rendering uses a small shared ECS helper. |

## Continuation Rules

1. Check `git status --short` before editing and preserve user-owned worktree
   changes.
2. Pick one coherent slice and make the smallest complete change.
3. Keep docs aligned with the actual repo shape.
4. Verify with the relevant local checks.
5. Commit only related files.
6. Do not add runbooks or drills unless they replace stale material or document
   an operator action someone can actually run.
7. Move durable facts into canonical docs; leave this file as a tracker.
8. Remove stale helpers, duplicate explanations, and dead path filters in the
   same slice that makes them obsolete.
9. Keep workflow and Terraform separation where it protects real review and
   ownership boundaries; merge only when duplication is truly noise.

## Documentation Ownership

- `README.md` is the short public project entrypoint.
- `docs/README.md` is the canonical grouped documentation map.
- `docs/roadmaps.md` tracks state, current work, decisions, and deferred work.
- Keep detailed ownership in `docs/README.md`; do not duplicate the full doc
  tree here.

## Decisions

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-18 | Reframe the repo as a platform monorepo seed. | The repo now distinguishes infrastructure catalog, platform concerns, and workload examples without introducing a private framework or a rewrite. |
| 2026-05-18 | Keep AWS-first portability by boundary as the default. | The repo should stay lean, standards-based, and runtime-specific until a real second-runtime need appears. |
| 2026-05-13 | Retire the ECS-hosted LGTM/FireLens stack. | Learning value is in standard telemetry contracts and dashboards, not hand-wiring Grafana, Loki, Prometheus, Tempo, ALBs, service discovery, IAM, and storage in Terraform. |
| 2026-05-13 | Use workload metadata for image build orchestration. | The workload contract should be the source of truth for buildable images, while the workflow supplies cloud credentials and registry resolution. |
| 2026-05-12 | Keep incident evidence portable and operator-readable. | Incident response needs clean labels, query hints, and deploy context without cloud-only Grafana features. |
| 2026-05-05 | Use Dapr pub/sub as the order event transport boundary. | The app keeps domain/outbox semantics while Dapr absorbs broker integration and leaves room for future service extraction. |
| 2026-05-02 | Complete the Terraform split and remove the legacy root. | Platform and app resources have different lifecycles; duplicate ownership invites drift. |
| 2026-05-02 | Keep docs canonical instead of session-shaped. | Roadmap notes are temporary; permanent docs should be short, current, and operator-owned. |
| 2026-04-30 | Prefer maintained tooling over bespoke quality scripts. | Standard tools reduce cognitive load and avoid custom mini-linters. |
| 2026-04-30 | Use split manual workflows for cloud changes. | Terraform plans and app build/scan results should be reviewed before separate apply/deploy triggers. |

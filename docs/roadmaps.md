# Roadmap

This file is the current continuation guide for platform, infrastructure,
DevOps, observability, data-flow, incident, rollout, async, and operator work.
Keep it short and current; retire session notes once their durable facts have
landed in canonical docs or code.

For the working style, use [Engineering Loop](engineering-loop.md). This
roadmap is the tracker; the engineering loop is the operating method.

## Current Status

The repository is a lean AWS delivery sandbox around one intentionally simple
order/customer workload:

- FastAPI API with `/health`, `/ready`, `/metrics`, request ID propagation,
  runtime `READ_MODE` and `WRITE_MODE` switches, and optional
  `Idempotency-Key` support for `POST /orders`.
- Durable order event outbox with a Dapr-enabled order event relay/consumer
  service, AWS SNS/SQS FIFO delivery, duplicate receipts, and stale-event
  handling.
- Checkpointed backfill worker with bounded pause/resume runs.
- Scheduled ECS data export job with raw CSV output, validated manifests, and
  S3 data hub publishing.
- Split Terraform roots: platform owns VPC networking, endpoints, domain/account
  lookups, and GitHub OIDC/CI IAM; app owns ECS, RDS, ALB/API edge, ECR, S3
  data hub, Dapr-backed SNS/SQS order events, EventBridge, CloudWatch app
  alarms, and optional observability.
- Local Prometheus, Loki, Promtail, and Grafana observability profile.
- Portable incident evidence bundles that collect ECS, alarm, deploy, and
  Grafana-stack query context without depending on managed Grafana AI features.
- A documented portable app/platform contract for workload images, health,
  readiness, metrics, logs, traces, config, release evidence, and rollback
  categories before adding another runtime target.
- A runtime capability contract for appendable hosting targets: networking,
  identity, secrets, ingress, observability, jobs, rollout, rollback, release
  evidence, cost controls, Terraform ownership, and local/CI guardrails.
- A database portability contract that treats PostgreSQL semantics as the app
  contract and RDS as the current AWS runtime implementation.
- Portable toolkit checklists for adding workloads, Dapr eventing, config and
  secrets, observability, CI quality gates, and data/object storage behavior.
- Dedicated portability contracts for workload onboarding, Dapr eventing,
  config/secrets, observability onboarding, reusable CI quality gates, and
  data/object storage.
- Documented portability boundaries: app code, local runtime, observability
  assets, and incident evidence are portable; AWS and GitHub Actions remain
  intentional provider dependencies at the platform/delivery edges.
- Runbooks and drills under `docs/runbooks/` and `docs/drills/` for deployment
  rollback, app health, app edge symptoms, RDS pressure, data export failures,
  dependency readiness, and order event queue failures.
- Local and CI checks for Ruff, Pyright, pytest, Terraform, TFLint, Checkov,
  Semgrep CE, Trivy, dependency audit, secret scanning, docs links, workflow
  linting, Dockerfile linting, and shell syntax.

The reference workload remains the zero-downtime schema evolution from
`orders.billing_email` to `order_contact_email`: expand, dual-write, backfill,
switch reads, new writes, and contract.

## Work Tracker

| Status | Step | Notes |
|---|---|---|
| Current | Harden the app-owned Grafana/Loki/Tempo/Prometheus contract. | Keep the baseline OSS-portable: app-owned logs, metrics, traces, dashboards, and incident evidence should work without Grafana Cloud AI or a CloudWatch Grafana datasource. |
| Current | Keep the portability boundary explicit. | See `docs/portability-status.md`: the app and observability evidence should travel, while AWS runtime infrastructure and GitHub Actions orchestration stay isolated provider edges. |
| Current | Keep the portable app/platform contract explicit. | See `docs/platform-contract.md`: future apps and runtime targets should satisfy the workload contract before adding EKS, another cloud, or cheaper compute. |
| Current | Keep the runtime capability contract explicit. | See `docs/runtime-capability-contract.md` and `platform/runtime-capabilities.json`: future runtime targets must satisfy the same capability set before being documented as supported. |
| Current | Keep database portability explicit. | See `docs/database-portability-contract.md`: workloads depend on PostgreSQL semantics, Liquibase, PgBouncer expectations, backup/restore, and secret injection; RDS is only the current AWS implementation. |
| Current | Keep the portable toolkit checklists current. | See `docs/portable-toolkit-checklists.md`: new workloads and runtime edges should reuse the same app, Dapr, config, observability, CI, and data-object-storage expectations. |
| Current | Keep dedicated toolkit contracts current. | See `docs/workload-onboarding-contract.md`, `docs/dapr-portability-contract.md`, `docs/config-secrets-contract.md`, `docs/observability-onboarding-contract.md`, `docs/ci-quality-contract.md`, and `docs/data-object-storage-portability.md`. |
| Current | Keep delivery rollback boundaries explicit. | App and data rollback drills are workflows; infra rollback uses reviewed `Infra Plan`/`Infra Apply`; completed one-off migration workflows are removed after execution. |
| Done | Clean Architecture package shape. | The repo now uses `apps/*` hosts with `packages/domain`, `packages/application`, and `packages/infrastructure`, plus ownership-aligned tests and docs. |
| Next | Revisit CloudWatch reduction toggles after dual-run. | Do not disable CloudWatch yet. Only app symptom and data-export success alarms have reduction toggles. |
| Current | Introduce Dapr as the app transport boundary. | First slices move order event relay/consume behind Dapr pub/sub and add bounded Dapr resiliency while keeping Terraform-owned AWS SNS/SQS and the durable outbox. |
| Waiting | Decide broader Dapr platform scope. | Candidate next slices: secrets/configuration, service invocation for extracted modules, and workflow orchestration for long-running application jobs. |
| Deferred | Data analytics stack work. | Do not add DuckDB, dbt, dlt, or analytics orchestration until the app/infra roadmap asks for it. |
| Done | Local development workflow housekeeping. | The repo is devcontainer-first, keeps `compose.yaml` as the root Compose contract, removes host-specific dependency manifests, and shares observability assets from `observability/`. |
| Recovered | App observability deploy drift. | Recovered by reconciling `infra/app`, fixing Cloud Map replacement noise, using a Secrets Manager ARN for Grafana, and verifying all ECS services steady. |
| Done | Platform/app Terraform split. | Platform owns VPC, endpoints, Route 53 lookup, and GitHub OIDC/CI IAM. App owns RDS, ECS, ALB/API edge, workload resources, CloudWatch app alarms, and optional observability. |
| Done | Local observability parity. | Local Prometheus/Loki/Tempo/Grafana profile is the app observability contract for logs, metrics, and traces. |

## Continuation Rules

1. Check `git status --short` before editing and preserve user-owned worktree
   changes.
2. Pick one coherent slice and make the smallest complete change.
3. Keep docs aligned with the actual repo shape.
4. Verify with the relevant local checks.
5. Commit only related files.
6. Do not add new runbooks or drills unless they replace stale material or
   document an operator action someone can actually run.
7. Keep roadmap rows current. Move completed facts into `Done`, open questions
   into `Waiting`, and failed-but-recovered work into `Recovered`.

## Documentation Ownership

- `README.md` is the short project index.
- `docs/engineering-loop.md` explains how to continue work cleanly.
- `docs/architecture.md` keeps long-form design rationale.
- `docs/architecture-layout.md` explains the current repo/control-boundary
  layout from GitHub automation through app, infra, scripts, tests, and docs.
- `docs/platform-contract.md` defines the portable workload contract for future
  apps and runtime targets.
- `docs/runtime-capability-contract.md` defines the runtime capability contract
  for future hosting targets.
- `docs/runtime-addition-checklist.md` turns that contract into the operator
  checklist for appending a future runtime.
- `docs/database-portability-contract.md` defines the PostgreSQL-compatible
  database contract and keeps RDS at the provider edge.
- `docs/portable-toolkit-checklists.md` captures the lean reusable checklist for
  future workloads and provider edges.
- The dedicated toolkit contracts split the checklist into stable operator
  references for workload onboarding, Dapr, config/secrets, observability, CI,
  and data/object storage.
- `docs/portability-status.md` states what is portable, what is intentionally
  provider-specific, and which portability gaps remain.
- `docs/deployment.md` is the detailed AWS operator runbook.
- `docs/local-development.md` is the local migration walkthrough.
- `docs/devops-toolchain.md` explains quality gates and CI/CD conventions.
- `docs/observability.md` explains Prometheus, Loki, Grafana, and CloudWatch
  signals.
- `docs/data-flow.md` explains the migration and data export flow.
- `docs/runbooks/` contains concrete incident runbooks.
- `docs/drills/` contains rehearsal procedures.
- `infra/README.md` explains the Terraform platform/app roots.

## Decisions

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-05 | Use Dapr pub/sub as the order event transport boundary. | The app keeps modular monolith domain and outbox semantics, while Dapr absorbs broker integration and leaves room for future service extraction. |
| 2026-05-05 | Keep Dapr adoption foundational but lean. | Dapr should create portable application-layer foundations for future complexity, but each building block should enter when it clarifies a real boundary or operation. |
| 2026-05-12 | Keep incident evidence portable and assistant-ready. | Grafana Assistant-style workflows need clean labels, query hints, and deploy context, but the baseline should remain Prometheus/Loki/Tempo/Grafana plus Markdown/JSON evidence bundles. |
| 2026-05-02 | Make the local workflow devcontainer-first and keep Compose at the root. | The dev container is the reproducible dependency environment, while `compose.yaml` is the standard local runtime contract that Docker tooling discovers automatically. |
| 2026-05-02 | Complete the Terraform split and remove the legacy root. | Platform and app now deploy from separate state keys; keeping the old root would invite accidental duplicate ownership. |
| 2026-05-02 | Keep docs canonical instead of session-shaped. | Roadmap sessions are useful while working, but permanent docs should be short, current, and operator-owned. |
| 2026-05-01 | Split Terraform into platform/bootstrap and app roots before ECS Grafana-stack deployment. | VPC and GitHub OIDC have a different lifecycle from RDS, ECS compute, ALB/API edge, workload resources, and observability; the app-owned stack needs a clean deployment root before observability can be runtime-validated. |
| 2026-04-29 | Keep one Terraform root until lifecycle boundaries become real. | Multiple stacks add naming, state, workflow, and documentation overhead before the project has repeated infrastructure shape. |
| 2026-04-29 | Use an evolutionary monorepo structure. | The safe-rollout demo should remain usable while the repo shape improves. |
| 2026-04-29 | Keep the application domain simple. | The value is in ECS delivery, data safety, DevOps practices, and operator maturity, not broad business features. |
| 2026-04-29 | Prefer Prometheus, Loki, and Grafana locally while using CloudWatch for AWS alarms. | The repo demonstrates local open-source observability and AWS-native operator signals. |
| 2026-04-29 | Add folders only with real content. | Empty top-level `ops/`, `security/`, `deploy/`, or package placeholders create ownership noise. |
| 2026-04-29 | Use one Dapr-backed order event before broadening async scope. | The event, idempotency key, broker transport, DLQ, metrics, tests, and runbook prove async behavior without expanding the domain. |
| 2026-04-30 | Add one real order event relay/consumer instead of inline request publishing. | Async processing should practice outbox claiming, duplicate delivery, and late-arrival handling while keeping the order domain lean. |
| 2026-04-30 | Prefer maintained tooling over bespoke quality scripts. | Standard tools reduce cognitive load and avoid custom mini-linters. |
| 2026-04-30 | Use split manual workflows for cloud changes. | Terraform plans and app build/scan results should be reviewed before a separate apply/deploy trigger, without depending on paid environment reviewer gates. |

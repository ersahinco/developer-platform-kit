# Roadmap

This file is the current continuation guide for platform, infrastructure,
DevOps, observability, data-flow, incident, rollout, async, and operator work.
Keep it short and current; detailed design rationale belongs in the focused
docs under `docs/` and `infra/`.

## Current Status

The repository is a lean AWS delivery sandbox around one intentionally simple
order/customer workload:

- FastAPI API with `/health`, `/ready`, `/metrics`, request ID propagation,
  runtime `READ_MODE` and `WRITE_MODE` switches, and optional
  `Idempotency-Key` support for `POST /orders`.
- Durable order event outbox with an order event relay/consumer service,
  SQS FIFO delivery, duplicate receipts, and stale-event handling.
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
  Semgrep CE, Trivy, dependency audit, secret scanning, docs links, workflow
  linting, Dockerfile linting, and shell syntax.

The reference workload remains the zero-downtime schema evolution from
`orders.billing_email` to `order_contact_email`: expand, dual-write, backfill,
switch reads, new writes, and contract.

## Current Direction

- Keep the repo single-stack until separate lifecycle boundaries are real.
- Keep the current platform/operator story intact while the next pass improves
  `apps/` and `packages/`.
- Make the application layer more meaningful and production-shaped without
  adding artificial complexity.
- Prefer standard tools over custom policy scripts.
- Add folders, services, runbooks, dashboards, or checks only when they have a
  concrete owner and behavior.

## Continuation Rules

1. Check `git status --short` before editing and preserve user-owned worktree
   changes.
2. Pick one coherent slice and make the smallest complete change.
3. Keep docs aligned with the actual repo shape.
4. Verify with the relevant local checks.
5. Commit only related files.

## Documentation Ownership

- `README.md` is the short project index.
- `docs/architecture.md` keeps long-form design rationale.
- `docs/deployment.md` is the detailed AWS operator runbook.
- `docs/local-development.md` is the local migration walkthrough.
- `docs/devops-toolchain.md` explains quality gates and CI/CD conventions.
- `docs/observability.md` explains Prometheus, Loki, Grafana, and CloudWatch
  signals.
- `docs/data-flow.md` explains the migration and data export flow.
- `infra/README.md` explains the Terraform root and split criteria.
- `ops/` contains concrete drills and runbooks only.

## Decisions

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-29 | Keep one Terraform root until lifecycle boundaries become real. | Multiple stacks add naming, state, workflow, and documentation overhead before the project has repeated infrastructure shape. |
| 2026-04-29 | Use an evolutionary monorepo structure. | The safe-rollout demo should remain usable while the repo shape improves. |
| 2026-04-29 | Keep the application domain simple. | The value is in ECS delivery, data safety, DevOps practices, and operator maturity, not broad business features. |
| 2026-04-29 | Prefer Prometheus, Loki, and Grafana locally while using CloudWatch for AWS alarms. | The repo demonstrates local open-source observability and AWS-native operator signals. |
| 2026-04-29 | Add folders only with real content. | Empty `ops/`, `security/`, `deploy/`, or package placeholders create ownership noise. |
| 2026-04-29 | Use one SQS-backed order event before broadening async scope. | The event, idempotency key, queue, DLQ, metrics, tests, and runbook prove async behavior without expanding the domain. |
| 2026-04-30 | Add one real order event relay/consumer instead of inline request publishing. | Async processing should practice outbox claiming, duplicate delivery, and late-arrival handling while keeping the order domain lean. |
| 2026-04-30 | Prefer maintained tooling over bespoke quality scripts. | Standard tools reduce cognitive load and avoid custom mini-linters. |
| 2026-04-30 | Use split manual workflows for cloud changes. | Terraform plans and app build/scan results should be reviewed before a separate apply/deploy trigger, without depending on paid environment reviewer gates. |

## Recent Changelog

| Date | Work | Verification |
|---|---|---|
| 2026-04-29 | Added local observability, data export, operator runbooks, CloudWatch alarms, SAST, Dependabot, Trivy, and repo-wide Pyright. | Ran focused tests, Ruff, Pyright, Terraform fmt/validate, TFLint, Checkov, and docs checks as relevant. |
| 2026-04-29 | Added dependency-readiness drill, post-deploy verification, queue-backed order events, DLQ alarm, metrics, and order event runbook. | Ran Ruff, Pyright, focused pytest, Terraform fmt/validate, TFLint, Checkov, workflow/docs checks, and whitespace checks. |
| 2026-04-30 | Replaced bespoke quality scripts with standard tools and removed low-value wrapper tests. | Ran `bash -n`, `git diff --check`, Ruff, Pyright, dependency audit, and pytest. |

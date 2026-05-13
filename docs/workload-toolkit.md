# Workload Toolkit

Use this when adding a service, worker, scheduled job, or one-off job. The goal
is standardization without reinvention: a new workload should look familiar
because it uses the same industry-standard tools and repo contracts as existing
workloads, not because it depends on a hidden custom framework.

Every workload must be declared in `platform/workloads.json` before runtime
infrastructure is added for it. Run
`uv run python scripts/ci/validate_platform_contract.py` before opening a PR.

## Required Shape

| Area | Service expectation | Job expectation |
| --- | --- | --- |
| Source | `apps/<name>/main.py` and `apps/<name>/pyproject.toml`. | Same. |
| Image | `apps/<name>/Dockerfile`, `image.repository`, non-root user, no baked secrets. | Same. |
| Health | `/health` returns process liveness. | Not required unless the job exposes HTTP. |
| Readiness | `/ready` checks runtime dependencies and returns structured failures. | Not required unless the job exposes HTTP. |
| Metrics | `/metrics` exposes Prometheus text for request/error/latency and useful workload outcomes. | Emit structured job outcome events; add metrics only when a long-running job host exposes HTTP. |
| Logs | Structured logs with stable runtime labels and workload correlation fields. | Structured start, progress, success, and failure events. |
| Config | Env vars describe application intent and are declared in `platform/workloads.json`. | Same, including bounded job controls such as batch size, run ID, or max batches. |
| Secrets | Secret names are declared separately from env vars and injected by the runtime secret mechanism. | Same. |
| Rollback | `app_image` unless the workload changes data or runtime state. | Usually `idempotent_rerun_or_forward_fix` unless a stronger restore path is documented. |
| Evidence | Cloud-changing deploys emit release evidence. | Data-changing or cloud-changing workflow runs emit release evidence or job artifacts. |
| Tests | Add focused tests for app behavior, contract shape, and scripts before runtime wiring. | Same. |

Every workload also declares conformance env, runtime-secret placeholders,
expected log fields, and service port or job timeout in `platform/workloads.json`
so `make runtime-conformance` can prove the image from outside the container.

## Boundary Rules

- Keep business rules in `packages/domain` and `packages/application`.
- Keep SQL, Dapr, object storage, provider SDKs, and delivery adapters in
  `packages/infrastructure`, `infra/`, `scripts/`, or workflows.
- Prefer the standard tool's native interface at the owning edge: FastAPI for
  service HTTP, SQLAlchemy for SQL adapters, Dapr for app-facing pub/sub,
  Liquibase for schema change, Terraform for infrastructure, and OpenTelemetry
  plus Prometheus/Loki/Tempo/Grafana for telemetry.
- Add shared helper code only when multiple workloads need the same behavior or
  an application port is the clearer boundary.
- Do not add runtime infrastructure first and backfill the app contract later.
- Do not add provider-specific env names unless the value is owned by the
  platform edge and documented in the workload contract.

## Checklist

Use this compact checklist when adding a workload:

- Add `apps/<name>/main.py`, `apps/<name>/pyproject.toml`, and
  `apps/<name>/Dockerfile`.
- Add the workload to `platform/workloads.json`.
- Declare the image repository name there so build workflows do not need a
  second workload list.
- For services, expose `/health`, `/ready`, and `/metrics`.
- For jobs, emit structured start, progress, success, and failure events and
  document idempotency.
- Declare env vars, secret names, rollback category, and release evidence.
- Keep business behavior in `packages/domain` and `packages/application`.
- Keep SQL, Dapr, object storage, and provider adapters in
  `packages/infrastructure`.
- Reuse established package, config, Dockerfile, observability, and CI patterns
  before adding a new helper library or workflow.
- Add focused tests before adding runtime infrastructure.

## Related Edges

Dapr eventing is documented in [Dapr Portability Contract](dapr-portability-contract.md).
Config and secrets are documented in
[Config And Secrets Contract](config-secrets-contract.md). Observability
onboarding is documented in
[Observability Onboarding Contract](observability-onboarding-contract.md). CI
gates are documented in [CI Quality Contract](ci-quality-contract.md). Data and
object storage expectations are documented in [Data](data.md).

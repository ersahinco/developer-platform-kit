# Workload Onboarding Contract

Use this contract when adding a new service, worker, scheduled job, or one-off
job. It keeps future applications portable across the current ECS runtime and
any later EKS, Azure, GCP, Nomad, or cheaper compute target.

## Required Shape

Every workload must be declared in `platform/workloads.json` before runtime
infrastructure is added for it.

| Area | Service expectation | Job expectation |
| --- | --- | --- |
| Source | `apps/<name>/main.py` and `apps/<name>/pyproject.toml`. | Same. |
| Image | `apps/<name>/Dockerfile`, non-root user, no baked secrets. | Same. |
| Health | `/health` returns process liveness. | Not required unless the job exposes HTTP. |
| Readiness | `/ready` checks runtime dependencies and returns structured failures. | Not required unless the job exposes HTTP. |
| Metrics | `/metrics` exposes Prometheus text for request/error/latency and useful workload outcomes. | Emit structured job outcome events; add metrics only when a long-running job host exposes HTTP. |
| Logs | Structured logs with stable runtime labels and workload correlation fields. | Structured start, progress, success, and failure events. |
| Config | Env vars describe application intent and are declared in `platform/workloads.json`. | Same, including bounded job controls such as batch size, run ID, or max batches. |
| Secrets | Secret names are declared separately from env vars and injected by the runtime secret mechanism. | Same. |
| Rollback | `app_image` unless the workload changes data or runtime state. | Usually `idempotent_rerun_or_forward_fix` unless a stronger restore path is documented. |
| Evidence | Cloud-changing deploys emit release evidence. | Data-changing or cloud-changing workflow runs emit release evidence or job artifacts. |
| Tests | Add focused tests for app behavior, contract shape, and scripts before runtime wiring. | Same. |

## Boundary Rules

- Keep business rules in `packages/domain` and `packages/application`.
- Keep SQL, Dapr, object storage, provider SDKs, and delivery adapters in
  `packages/infrastructure`, `infra/`, `scripts/`, or workflows.
- Do not add runtime infrastructure first and backfill the app contract later.
- Do not add provider-specific env names unless the value is owned by the
  platform edge and documented in the workload contract.
- Run `uv run python scripts/ci/validate_platform_contract.py` before opening a
  PR for a new workload.

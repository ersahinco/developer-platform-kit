---
inclusion: fileMatch
fileMatchPattern: "apps/**/*.py"
---

# Workload App Host Rules

Activated when working in any `apps/*/` directory.

## Rules

- `apps/` owns settings, routes, lifecycle, dependency wiring, and workload-level operational logs.
- Business logic belongs in `packages/`.
- SQL, Dapr, and AWS SDK calls belong in `packages/infrastructure/`.
- Every config value is environment-variable-backed and declared in `platform/workloads.json`.
- Services expose `/health`, `/ready`, `/metrics`.
- Jobs exit meaningfully, emit structured events, and document idempotency.
- Register workloads in `platform/workloads.json` before Terraform resources.
- Reuse `platform/workload.Dockerfile` unless the workload README says why not.

# apps/ Rules

Root `AGENTS.md` applies here too.

## Keep apps/ Thin

Belongs here:

- `config.py` / `Settings`
- routes and schemas
- startup, shutdown, background task registration
- dependency wiring
- workload-level operational logs

Does not belong here:

- business logic -> `packages/application/` or `packages/domain/`
- SQL and ORM session management -> `packages/infrastructure/`
- Dapr or AWS SDK calls -> `packages/infrastructure/`
- shared utilities -> `packages/`

If an `apps/` file grows beyond settings, wiring, and routes, extract it.

## Rules

- Every config value is environment-variable-backed.
- Declare config and secret names in `platform/workloads.json` first.
- Prefer intent names like `DATABASE_URL`, `PUBSUB_NAME`, `EXPORT_BUCKET_NAME`.
- Never log secret values.
- Services expose `/health`, `/ready`, `/metrics`.
- Jobs exit meaningfully, emit structured events, and document idempotency.
- Register the workload in `platform/workloads.json` before Terraform resources.
- Reuse `platform/workload.Dockerfile` unless a workload README explains why not.

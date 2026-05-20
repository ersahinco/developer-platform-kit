---
inclusion: fileMatch
fileMatchPattern: "apps/**/*.py"
---

# Workload App Host Rules

Activated when working in any `apps/*/` directory.

`apps/` contains reference workload hosts — the runnable wiring layer. Keep it thin.

---

## What Belongs in apps/

- Runtime settings (`config.py` / `Settings` class backed by environment variables)
- HTTP route definitions and schema types (FastAPI routers)
- Process lifecycle: startup, shutdown, background task registration
- Dependency assembly: wire concrete infrastructure adapters to application ports
- Workload-level operational events: structured start, ready, shutdown logs

## What Does NOT Belong in apps/

- Business logic — move it to `packages/application/` or `packages/domain/`
- SQL queries or ORM session management — move to `packages/infrastructure/`
- Dapr component calls — move to `packages/infrastructure/dapr/`
- AWS SDK calls — move to `packages/infrastructure/` or platform edge scripts
- Shared utilities used by more than one workload — move to `packages/`

**Trigger**: If an `apps/` file grows beyond settings + wiring + routes, extract the behavior into the appropriate package layer.

---

## Settings / Config Rules

- Every config value must be backed by an environment variable
- Declare the config and secret names in `platform/workloads.json` first
- Prefer names that describe application intent, not provider plumbing
  - Good: `DATABASE_URL`, `PUBSUB_NAME`, `EXPORT_BUCKET_NAME`
  - Avoid: `RDS_ENDPOINT`, `SQS_QUEUE_ARN`, `S3_BUCKET_ARN`
- Never read secrets from files committed to the repo
- Never log secret values — log key names only

---

## Service Workload Requirements (edge-service, internal-service)

Every service workload host must expose:

```python
GET /health   # liveness — is the process alive?
GET /ready    # readiness — is the process ready to serve traffic?
GET /metrics  # Prometheus text format
```

- `/health` must return 200 when the process is alive
- `/ready` must return 200 only when all dependencies are reachable and the workload can serve
- `/metrics` must expose Prometheus-compatible metrics
- Structured logs must include stable workload identifiers (workload name, version, environment)

---

## Job Workload Requirements (operator-job, scheduled-job)

Every job workload host must:

- Exit with a meaningful status code (0 = success, non-zero = failure)
- Emit structured events at start, progress milestones, success, and failure
- Be safe to rerun — document idempotency bounds explicitly in the workload
- Apply the same config and secret rules as service workloads

---

## Shared Workload Dockerfile

Use `platform/workload.Dockerfile` unless there is a documented reason not to.
If a workload needs a custom Dockerfile, document why in the workload's README.

---

## platform/workloads.json — Register Before Infra

Add the workload to `platform/workloads.json` **before** creating any Terraform resources.
The spec owns workload identity; `infra/app/` fulfills it.

Required fields for a new workload entry:
- `name` and `kind` (operational class)
- `host` path under `apps/`
- Service port (for HTTP workloads)
- Declared config and secret names
- Portable health, metrics, and idempotency expectations

---

## Final Check Before Committing App Changes

- [ ] `apps/` file is thin — business logic lives in `packages/`
- [ ] All config values are environment-variable-backed and declared in `platform/workloads.json`
- [ ] Service workloads expose `/health`, `/ready`, `/metrics`
- [ ] Job workloads emit structured events and document idempotency
- [ ] `make runtime-conformance` passes

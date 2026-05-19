# apps/ — Workload Host Rules

Scoped rules for all workload hosts under `apps/`.
The cross-tool base rules in root `AGENTS.md` apply here too.

---

## What Belongs in apps/

- Runtime settings (`config.py` / `Settings` backed by environment variables)
- HTTP route definitions and schema types (FastAPI routers)
- Process lifecycle: startup, shutdown, background task registration
- Dependency assembly: wire concrete infrastructure adapters to application ports
- Workload-level operational events: structured start, ready, shutdown logs

## What Does NOT Belong in apps/

- Business logic → `packages/application/` or `packages/domain/`
- SQL queries or ORM session management → `packages/infrastructure/`
- Dapr component calls → `packages/infrastructure/dapr/`
- AWS SDK calls → `packages/infrastructure/` or platform edge scripts
- Shared utilities used by more than one workload → `packages/`

If an `apps/` file grows beyond settings + wiring + routes, extract the behavior.

---

## Settings Rules

- Every config value backed by an environment variable
- Declare config and secret names in `platform/workloads.json` first
- Prefer intent-describing names: `DATABASE_URL`, `PUBSUB_NAME`, `EXPORT_BUCKET_NAME`
- Avoid provider-plumbing names: `RDS_ENDPOINT`, `SQS_QUEUE_ARN`, `S3_BUCKET_ARN`
- Never log secret values — log key names only

---

## Service Workload Requirements (edge-service, internal-service)

```
GET /health   → 200 when process is alive
GET /ready    → 200 only when all dependencies reachable and workload can serve
GET /metrics  → Prometheus text format
```

Structured logs must include stable workload identifiers (name, version, environment).

---

## Job Workload Requirements (operator-job, scheduled-job)

- Exit 0 on success, non-zero on failure
- Emit structured events at start, progress milestones, success, and failure
- Safe to rerun — document idempotency bounds explicitly
- Same config and secret rules as service workloads

---

## platform/workloads.json — Register Before Infra

Add the workload to `platform/workloads.json` **before** creating any Terraform resources.
Required fields: `name`, `kind` (operational class), `host` path, service port (HTTP workloads),
declared config and secret names, portable health/metrics/idempotency expectations.

---

## Shared Dockerfile

Use `platform/workload.Dockerfile` unless there is a documented reason not to.
If a custom Dockerfile is needed, document why in the workload's README.

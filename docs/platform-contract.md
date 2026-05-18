# Platform Contract

This is the portable application contract for this repository. It describes
what a workload must provide to run on the current platform shape without
pretending the runtime is cloud-neutral.

The project goal is an opinionated delivery toolkit, not a private framework.
Use standard tools directly and keep provider details at the platform edge.

`platform/workloads.json` is the machine-readable workload registry.
Focused pytest checks and `make runtime-conformance` are the main proof that the
declared workloads still satisfy the contract.

## Workload Shape

Every service workload must provide:

- A committed OCI image declared in `platform/workloads.json`
- A stable app package under `apps/`
- `/health`, `/ready`, and `/metrics`
- Prometheus metrics
- Structured logs with stable runtime labels and workload identifiers
- Environment-variable or mounted-file configuration
- Runtime secret injection without baking secret values into images
- Optional OTLP/HTTP traces when they materially help debugging

Every one-off or scheduled job must provide:

- A committed OCI image
- Meaningful process exit status
- Safe rerun behavior or clearly bounded idempotency
- Structured start, progress, success, and failure events
- The same config and secret rules as services

Current long-running workloads are `apps/api` and `apps/order_event_consumer`.
Current job workloads are `apps/backfill_worker` and `apps/data_export_job`.

## Workload Checklist

- Add `apps/<name>/main.py`, `config.py`, and `pyproject.toml`
- Add the workload to `platform/workloads.json` before adding runtime-specific
  infrastructure
- Reuse the shared workload Dockerfile unless there is a real need not to
- For services, expose `/health`, `/ready`, and `/metrics`
- For jobs, emit structured success and progress events and document
  idempotency
- Add focused pytest coverage and keep `make runtime-conformance` passing

## Boundaries

- `packages/domain`: pure business behavior
- `packages/application`: use cases and stable ports
- `packages/infrastructure`: SQL, storage, Dapr, and provider adapters
- `apps/*`: runtime wiring, settings, HTTP routes, and entrypoints
- `infra/`, `scripts/`, and workflows: provider and delivery edges

Provider resource names such as buckets, queues, task definitions, and IAM
roles belong at the platform edge, not in domain or application code.

## Configuration And Secrets

- Declare workload config and secrets in `platform/workloads.json`
- Prefer names that describe application intent rather than provider plumbing
- Keep secret values out of committed files, Docker layers, tfvars, and logs
- Keep `Settings` aligned with declared environment variables
- Use full URLs where they simplify local and test ergonomics

Database expectations are defined by PostgreSQL-compatible behavior, Liquibase
migrations, PgBouncer expectations, and runtime secret injection. RDS is the
current implementation, not the portable contract.

## Eventing

Dapr is the app-facing eventing boundary in this repo.

- Application code can know Dapr pub/sub names, topics, CloudEvents, and
  outbox semantics
- Application code should not know whether the runtime uses SNS/SQS, Redis,
  Kafka, Azure Service Bus, GCP Pub/Sub, or another broker
- The durable application handoff remains the database outbox
- Retry, dead-letter, and idempotency behavior must stay explicit

Dapr is intentional here because it standardizes platform capabilities while
keeping broker choice at the runtime edge. Do not broaden it into unrelated
capabilities until a real workload needs them.

## Observability

The portable observability baseline is:

- Prometheus-compatible metrics
- Loki-compatible structured logs
- OTLP/HTTP traces when enabled
- Grafana dashboards without a provider-locked datasource requirement

CloudWatch remains the AWS-native signal source for rollback and managed
infrastructure alarms. It is allowed at the platform edge, but it is not the
portable app observability contract.

## Delivery And Evidence

Delivery is review-first:

- Build before deploy
- Plan before apply
- Use immutable image tags
- Emit release evidence for cloud-changing workflows

The durable record is the release event: what changed, which revision ran,
which workflow applied it, what verification happened, and which alarms were
observed.

## Rollback

Keep rollback categories separate:

- App image rollback
- Runtime data-phase rollback
- Infra rollback through reviewed plan/apply
- Job recovery through idempotent rerun, forward fix, or documented data restore

Future runtimes can change the implementation details, but they should preserve
those ownership categories.

# Platform Contract

This is the portable workload contract for this repository. It describes what a
workload example must provide to run on the current platform shape without
pretending the runtime is cloud-neutral.

The project goal is an opinionated platform monorepo seed, not a private
framework. Use standard tools directly and keep provider details at the
platform edge.

`platform/workloads.json` is the temporary machine-readable application
specification. Focused pytest checks and `make runtime-conformance` are the main
proof that the declared workloads still satisfy the contract.

## Application Specification

`platform/workloads.json` currently owns:

- workload identity and kind
- workload host location under `apps/`
- workload operational class such as public edge, internal service, scheduled
  job, or operator-run job
- service port declarations for HTTP workloads
- Dapr app identity and component mappings when a workload uses Dapr
- shared image package and command metadata
- portable health, metrics, traces, and idempotency expectations
- workload-facing config and secret names

It currently does not own:

- provider-specific resource names
- AWS queue, topic, bucket, ALB, ECS, IAM, or RDS implementation details
- Dapr component backing implementations for a given environment profile
- Terraform composition or GitHub Actions deployment choreography
- runtime-conformance fixture values used only by the local/CI container checks

This file is intentionally transitional. The long-term direction is still to
let workloads declare what they need once while platform and runtime layers own
how those needs are fulfilled.

## Metadata Ownership

Keep the metadata model to three layers only:

- `platform/workloads.json` defines what the workload is: identity,
  operational class, app path, shared image metadata, declared config names,
  service port shape, Dapr intent, and portable expectations
- `platform/runtime-conformance.json` defines local/CI fixture data only for
  `make runtime-conformance`
- `infra/app/workload_inventory.tf` defines how the current AWS runtime
  fulfills that contract with runtime values, secret wiring, and AWS-facing
  naming derived from the workload contract

Ownership rule:

- contract metadata defines what the workload is
- runtime inventory defines how AWS fulfills it

Do not let `platform/runtime-conformance.json` grow second application-spec
semantics, and do not let `infra/app/workload_inventory.tf` redefine workload
identity or capability intent.

## Workload Shape

Every service workload must provide:

- A committed OCI image declared in `platform/workloads.json`
- A stable reference host package under `apps/`
- A declared HTTP service port in the application specification
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

Current long-running reference workloads are `apps/api` and
`apps/order_event_consumer`. Current job workloads are
`apps/backfill_worker` and `apps/data_export_job`.

## Operational Class

The workload specification must declare the operational class for each
workload so future additions do not rely on imitation or repo folklore.

- `edge-service`: a user-facing or externally routed HTTP service
- `internal-service`: a long-running service without public edge ownership
- `operator-job`: a one-off task triggered manually or by CI/operator workflow
- `scheduled-job`: a recurring task triggered by a scheduler

Current reference mapping:

- `api` is an `edge-service`
- `order_event_consumer` is an `internal-service`
- `backfill_worker` is an `operator-job`
- `data_export_job` is a `scheduled-job`

This classification is part of the portable contract. Runtime-specific details
such as ALB, ECS service count, EventBridge Scheduler, or manual operator
workflow still belong at the platform edge.

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
- `apps/*`: reference workload wiring, settings, HTTP routes, and entrypoints
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
- The application specification can declare Dapr app identity and component
  mappings
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

Alarm ownership rule:

- workloads declare observable behavior and runtime class
- platform concerns decide which CloudWatch alarms, release snapshots, and
  incident snapshots protect those behaviors in the current runtime

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

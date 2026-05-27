# Platform Contract

Portable workload contract for this repo.

Goal: keep the workload contract as part of the stable center of the platform so
workloads run on current and future runtime targets without leaking provider
details into app code. Use standard tools directly and keep provider details at
the platform edge.

`platform/workloads.json` is the machine-readable workload contract.
`platform/workload-patterns.json` is the machine-readable list of supported
workload classification shapes.
Focused pytest checks plus `make runtime-conformance` are the main proof that
declared workloads still satisfy the contract.

## Stable Center

- The workload contract is the canonical definition of workload intent.
- The platform catalog supplies reusable capabilities that realize that intent.
- Runtime targets may vary, but they must realize the contract instead of
  redefining workload meaning.

## Canonical Contract

`platform/workloads.json` owns:

- workload identity and kind
- target-neutral workload use cases for discovery and templates
- workload owner
- host location under `apps/`
- supported runtime targets and admitted runtime targets
- operational class
- service port declarations
- optional capability declarations such as database or Dapr when the workload actually needs them
- Dapr app identity and component mappings
- shared image package and command metadata
- portable health, metrics, traces, and idempotency expectations
- workload-facing config and secret names

`platform/workload-patterns.json` owns:

- reusable workload shape names such as `edge-service`, `internal-async-service`, `scheduled-job`, and `export-job`
- the kind and operational-class alignment for those shapes
- a small shared vocabulary for catalog and self-service discovery

It does not own:

- required workload fields; those belong in the workload contract and its policy checks
- provider and runtime resource names
- AWS queue, topic, bucket, ALB, ECS, IAM, or RDS details for the current target
- Dapr component backing implementations for an environment profile
- Terraform composition or GitHub Actions deployment choreography
- `platform/runtime-conformance.json` fixture values

## Metadata Ownership

Three ownership layers for the current AWS target:

1. `platform/workloads.json`: what the workload is
2. `platform/runtime-conformance.json`: local/CI fixture data only
3. `infra/app/workload_inventory.tf`: how the current AWS runtime fulfills the contract

Rules:

- Do not let `platform/runtime-conformance.json` grow second application-spec semantics.
- Do not let runtime realization layers such as `infra/app/workload_inventory.tf` redefine workload identity or capability intent.
- Future runtime targets add parallel realization layers; they do not replace
  the stable center.

## Workload Shape

In addition to `kind` and operational class, each workload declares one or more
target-neutral `use_cases`. These help catalog, template, and self-service
surfaces distinguish workloads like `http-api`, `event-consumer`, `dashboard`,
or `connector` without encoding runtime details.

Each workload also declares one or more stable-center `patterns`. These support
classification and discovery while keeping reusable workload shapes explicit
instead of hiding them in Terraform locals or workflow conditionals.

Each workload declares runtime support explicitly:

- `runtime.supported`: runtime targets the workload host can run on today
- `runtime.admitted`: runtime targets with reviewed realization and delivery ownership
- `owner`: the team that owns workload operation and runtime admission decisions

Support and admission are intentionally different. A workload may be a real
contract-governed app host under `apps/` with only `local-compose` support.

Service workloads must provide:

- committed OCI image declared in `platform/workloads.json`
- stable host package under `apps/`
- declared HTTP service port
- `/health`, `/ready`, `/metrics`
- Prometheus metrics
- structured logs with stable runtime labels and workload identifiers
- environment-variable or mounted-file configuration
- runtime secret injection without baking secrets into images
- optional OTLP/HTTP traces when they materially help debugging

Job workloads must provide:

- committed OCI image
- meaningful process exit status
- safe rerun behavior or clearly bounded idempotency
- structured start, progress, success, and failure events
- the same config and secret rules as services

Current long-running workloads:

- `apps/api`
- `apps/event_consumer`

Current jobs:

- `apps/backfill_worker`
- `apps/data_export_job`
- `apps/open_dataset_pipeline`

## Operational Class

| Class | Meaning |
|---|---|
| `edge-service` | user-facing or externally routed HTTP service |
| `internal-service` | long-running service without public edge ownership |
| `operator-job` | one-off task triggered manually or by CI/operator workflow |
| `scheduled-job` | recurring task triggered by a scheduler |

Current mapping:

- `api`: `edge-service`
- `event_consumer`: `internal-service`
- `backfill_worker`: `operator-job`
- `data_export_job`: `scheduled-job`

Runtime details like ALB, ECS service count, EventBridge Scheduler, managed
Kubernetes manifests, or manual operator flow stay at the platform edge.

## Workload Checklist

- Add `apps/<name>/main.py`, `config.py`, and `pyproject.toml`
- Add the workload to `platform/workloads.json` before runtime-target-specific infrastructure
- Declare a portable workload owner before adding cloud runtime admission
- Reuse the shared workload Dockerfile unless there is a real reason not to
- Services expose `/health`, `/ready`, and `/metrics`
- Jobs emit structured success and progress events and document idempotency
- Add focused pytest coverage and keep `make runtime-conformance` passing

## Boundaries

- `packages/domain`: pure business behavior
- `packages/application`: use cases and stable ports
- `packages/infrastructure`: SQL, storage, Dapr, provider adapters
- `apps/*`: workload wiring, settings, routes, entrypoints
- `infra/`, `scripts/`, workflows: runtime-target and delivery edges

Provider resource names such as buckets, queues, task definitions, and IAM
roles belong at the platform edge, not in domain or application code.

## Configuration And Secrets

- Declare workload config and secrets in `platform/workloads.json`
- Prefer application-intent names over provider-plumbing names
- Keep secret values out of committed files, Docker layers, tfvars, and logs
- Keep `Settings` aligned with declared environment variables
- Use full URLs where they simplify local and test ergonomics

Database expectations apply only to workloads that declare the database
capability. For those workloads, the portable contract is PostgreSQL-compatible
behavior, Liquibase migrations, PgBouncer expectations where needed, and
runtime secret injection. RDS is the current AWS implementation, not the
portable contract.

## Eventing

Dapr is the app-facing eventing boundary.

- Application code may know Dapr pub/sub names, topics, CloudEvents, and outbox semantics.
- The application specification may declare Dapr app identity and component mappings.
- Application code must not know whether runtime transport is SNS/SQS, Redis, Kafka, Azure Service Bus, GCP Pub/Sub, or another broker.
- The durable application handoff remains the database outbox.
- Retry, dead-letter, and idempotency behavior must stay explicit.

Do not broaden Dapr into unrelated capabilities until a real workload needs
them.

## Observability

Portable baseline:

- Prometheus-compatible metrics
- Loki-compatible structured logs
- OTLP/HTTP traces when enabled
- Grafana dashboards without provider-locked datasources

CloudWatch is allowed at the platform edge for rollback and managed
infrastructure alarms, but it is not the portable app observability contract.

Alarm ownership:

- workloads declare observable behavior and runtime class
- platform concerns choose the current runtime alarms, release snapshots, and incident snapshots

## Delivery And Evidence

Delivery is review-first:

- build before deploy
- plan before apply
- immutable image tags
- release evidence for cloud-changing workflows

The durable record is the release event: what changed, which revision ran,
which workflow applied it, what verification happened, and which alarms were
observed.

## Rollback

Keep rollback categories separate:

- app image rollback
- runtime data-phase rollback
- infra rollback through reviewed plan/apply
- job recovery through idempotent rerun, forward fix, or documented data restore

Future runtimes may change implementation details, but they should preserve
those ownership categories.

# Platform Contract

This is the portable application contract for this repository. It describes
what a workload must provide to run on the project platform shape today, without
claiming that the current runtime is cloud-neutral.

The project goal is an opinionated platform toolkit, not a private framework.
The contract aims for standardization without reinvention: it assembles
Docker/OCI images, FastAPI service hosts, Python packages, SQLAlchemy adapters,
Liquibase migrations, Dapr pub/sub, OpenTelemetry,
Prometheus/Loki/Tempo/Grafana, Terraform, GitHub Actions, and security/quality
scanners. Do not hide those tools behind custom abstractions unless the
abstraction is already a stable application port or removes real duplication
across workloads.

The machine-readable workload inventory lives in `platform/workloads.json` and
is enforced by `scripts/ci/validate_platform_contract.py`. Add future apps there
before adding runtime-specific infrastructure for them.

Database expectations live in `docs/data.md`. The app contract is
PostgreSQL-compatible behavior, Liquibase migrations, PgBouncer pooling
expectations, and runtime secret injection. RDS is the current AWS
implementation, not the portable application contract.

The current implementation target is ECS, Terraform, AWS-managed dependencies,
and GitHub Actions. Future runtimes such as Kubernetes, another cloud, or lower
cost compute should satisfy this contract before the repo adds another platform
root. Do not add a second runtime only to prove portability.

## Workload Shape

Every long-running app workload must provide this surface:

| Area | Contract |
| --- | --- |
| OCI image | A committed `apps/<name>/Dockerfile`, declared `image.repository` in `platform/workloads.json`, non-root runtime user, no secrets baked into layers, `PYTHONPATH`/entrypoint wiring that works from a clean image build. |
| App package | A stable app folder and import package under `apps/`; runtime wiring stays in `apps/*`, not in `packages/domain` or `packages/application`. |
| Liveness | `/health` returns `200` when the process can accept traffic, without requiring downstream dependencies. |
| Readiness | `/ready` checks required runtime dependencies and returns `503` with a structured failed check when the workload should be removed from rotation. |
| Metrics | `/metrics` exposes Prometheus text with request count, request latency, readiness/error status, and workload-specific outcome counters where useful. |
| Logs | Logs are JSON or parseable structured lines and preserve stable labels/correlation fields: `stack`, `environment`, `service`, `container`, `request_id`, and workload identifiers such as `event_id` or `job_name`. |
| Traces | OTLP/HTTP traces are optional per workload; add them when request or job spans materially help debugging. ECS routes API traces through the ADOT sidecar on localhost so the backend can change without changing app code. |
| Config | Runtime behavior is controlled by environment variables, mounted configuration, or application ports. Names should describe app intent, not provider plumbing, unless the value is owned by the platform edge. |
| Secrets | Sensitive values are injected by the runtime secret mechanism and consumed as environment variables or mounted files. They are not committed, logged, or baked into images. |

One-off and scheduled workloads should follow the same image, logging, config,
and evidence conventions. They do not need HTTP endpoints unless they expose a
service.

One-off and scheduled workloads must also be clear about:

| Area | Contract |
| --- | --- |
| Execution | They run from a committed OCI image and exit with a meaningful process status. |
| Idempotency | Re-runs are safe or explicitly bounded by job state, checkpoints, or input keys. |
| Logs | They emit structured start, progress, success, and failure events with stable job identifiers. |
| Config/secrets | They use the same environment and runtime secret injection rules as services. |
| Evidence | Cloud-changing or data-changing jobs produce artifacts or release events when run by delivery workflows. |

Current long-running workloads implementing this surface are `apps/api` and
`apps/order_event_consumer`. `apps/backfill_worker` and `apps/data_export_job`
remain one-off/scheduled workloads and should not grow HTTP endpoints just to
look like services.

Every workload also declares conformance env, runtime-secret placeholders,
expected log fields, and service port or job timeout in `platform/workloads.json`
so `make runtime-conformance` can prove the image from outside the container.

## Workload Checklist

Use this compact checklist when adding a service, worker, scheduled job, or
one-off job:

- Add `apps/<name>/main.py`, `apps/<name>/pyproject.toml`, and
  `apps/<name>/Dockerfile`.
- Add the workload to `platform/workloads.json` before adding runtime
  infrastructure for it.
- Declare the image repository name there so build workflows do not need a
  second workload list.
- For services, expose `/health`, `/ready`, and `/metrics`.
- For jobs, emit structured start, progress, success, and failure events and
  document idempotency.
- Declare env vars, secret names, rollback category, release evidence, required
  log fields, conformance env, and service port or job timeout.
- Keep business behavior in `packages/domain` and `packages/application`.
- Keep SQL, Dapr, object storage, provider SDKs, and delivery adapters in
  `packages/infrastructure`, `infra/`, `scripts/`, or workflows.
- Reuse established package, config, Dockerfile, observability, and CI patterns
  before adding a helper library or workflow.
- Run `uv run python scripts/ci/validate_platform_contract.py` and add focused
  tests before adding runtime infrastructure.

## Configuration And Secrets

Runtime configuration should enter through environment variables, mounted
configuration, or application ports. Sensitive values should be injected by the
runtime secret mechanism, not committed to the repo and not baked into images.

Application code should depend on domain/application ports where practical:

- `packages/domain` remains pure business behavior.
- `packages/application` owns use cases and stable ports.
- `packages/infrastructure` owns SQL, storage, pub/sub, Dapr, and provider
  adapters.
- `apps/*` owns runtime wiring, settings, HTTP schemas, and command entrypoints.

Provider-specific names such as buckets, queues, task definitions, and IAM roles
belong at platform/delivery edges, not in domain or application code.

Naming rules:

| Type | Rule |
| --- | --- |
| Env vars | Upper snake case, declared in `platform/workloads.json`, and named for application intent. |
| Secrets | Declared separately from env vars in `platform/workloads.json`; a name cannot be both config and secret. |
| Provider resources | Bucket, queue, task definition, IAM, and managed-service names stay at platform/delivery edges. |
| Runtime config | Operator-toggled behavior such as `READ_MODE` and `WRITE_MODE` belongs in the runtime config store. |
| Job controls | Batch size, sleep interval, max batches, run ID, and dates are explicit env vars. |

Configuration sources by environment:

| Environment | Source |
| --- | --- |
| Local | `.env`, Docker Compose env, local Postgres/PgBouncer, LocalStack for Dapr broker tests, and test overrides. |
| CI | GitHub Actions env and service containers for non-secret test values. |
| AWS runtime | ECS env, Secrets Manager injection, runtime config table, and Terraform-owned resource names. |
| Future runtime | Equivalent env/config/secret injection that satisfies the same workload contract. |

`platform/workloads.json` is the source of truth for local, CI, and runtime
shape. Each workload declares conformance env values for local container proof,
while secrets use `runtime-secret://` placeholders so the contract can prove the
name and injection edge without committing a secret value.

Guardrails:

- Prefer full URLs for local and test ergonomics.
- Allow composed `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, and injected
  `DB_PASSWORD` for runtimes that should not store full URLs in deployment
  config.
- Do not log secret values or generated URLs containing secret values.
- Keep workload `Settings` fields aligned with every env and secret declared in
  `platform/workloads.json`.
- Secret names may appear in runtime-edge wiring, but must not be assigned in
  Dockerfiles or committed env examples.

## Eventing

Dapr is the application-facing eventing boundary for this repo. Application
code should know Dapr pub/sub names, topics, CloudEvents, sidecar endpoints, and
outbox semantics. It should not know whether the current runtime implements
that component with SNS/SQS, Redis, Kafka, Azure Service Bus, GCP Pub/Sub, or
another broker.

| Area | Contract |
| --- | --- |
| Publish API | Application infrastructure adapters publish through the Dapr HTTP sidecar. |
| Subscribe API | Runtime services expose Dapr subscription metadata and handlers, not provider queue handlers. |
| Event shape | Events preserve stable names, IDs, CloudEvents metadata, and payload fields. |
| Durability | The application outbox remains the durable handoff from database commit to event relay. |
| Idempotency | Consumers record receipts or equivalent idempotency state before treating delivery as complete. |
| Resiliency | Dapr retry/circuit-breaker settings are bounded and component-scoped. |
| Observability | Relay and consume outcomes emit structured logs, Prometheus metrics when hosted, and release/incident evidence. |

The current runtime implements the `order-events-pubsub` Dapr component with
AWS SNS/SQS FIFO resources. Terraform owns the topic, queue, DLQ, encryption,
permissions, runtime component manifests, and SQS DLQ alarm. Those details stay
in `infra/`, `dapr/`, runbooks, and delivery scripts.

Provider-native SQS metrics are acceptable for the AWS platform edge. They must
not replace the app-facing Dapr/outbox contract or make app code import AWS
broker APIs.

Before changing the broker implementation or adding a runtime:

- Keep `ORDER_EVENTS_PUBSUB_NAME`, topic names, event names, and CloudEvents
  semantics stable unless every runtime should change.
- Keep provider component manifests outside domain/application code.
- Map the Dapr component to the runtime broker that fits the operating need.
- Keep retry, dead-letter, and idempotency behavior documented.
- Preserve incident evidence query hints for relay success, consume success,
  failures, and parked messages.
- Add contract tests before calling the new component supported. The
  `tests/fixtures/dapr/alternate-order-events-pubsub.yaml` fixture proves that
  a non-AWS Dapr component can keep the same `order-events-pubsub` application
  contract without changing app code.

Do not broaden Dapr into secrets, config, workflow, state, or service invocation
until a concrete workload needs that capability.

## Observability

The portable observability baseline is Prometheus, Loki, Tempo, Grafana, and
OpenTelemetry. Workloads should make these signals useful without a Grafana
Cloud dependency or a Grafana CloudWatch datasource:

- Metrics: request count, request latency, 5xx/error counts, readiness failures,
  and workload-specific outcomes.
- Logs: JSON or parseable structured lines with `stack`, `environment`,
  `service`, `container`, and relevant workload identifiers.
- Correlation: preserve `request_id` and emit `trace_id` when tracing is active.
- Delivery context: release events should include `runtime_id`, `workload_id`,
  `deployment_id`, `image_digest`, `source_workflow`, evidence links, status,
  and SLO timings.

CloudWatch remains the AWS-native alarm and managed-resource signal for the ECS
sandbox. Portable dashboards and app-owned telemetry should not require
CloudWatch queries.

Minimum new workload checklist:

- Add metrics names to `platform/workloads.json`.
- Add required log fields to `platform/workloads.json`.
- Decide whether traces are supported; use OTLP/HTTP if enabled.
- Make `/ready` expose dependency failure names for services.
- Add incident evidence query hints when the workload adds a new operator path.
- Update Grafana dashboards or document why existing dashboards cover the
  workload.

CloudWatch, Azure Monitor, Google Cloud Monitoring, or another provider-native
tool may be used for managed infrastructure signals. They should not become the
portable app observability contract.

## Delivery And Evidence

Delivery is review-first:

- Build before deploy.
- Plan before apply.
- Immutable image tags identify app revisions.
- Cloud-changing workflows emit release evidence artifacts.
- Evidence is Markdown/JSON/JSONL and can be pushed to Loki when reachable.

The evidence shape should outlive GitHub Actions. GitHub is the orchestrator
today, but the durable record is the release event: what changed, which revision
ran, which workflow or plan applied it, what verification happened, and which
alarms were observed.

Release evidence events must preserve a provider-neutral core, even when a
future runtime keeps provider-specific details in optional nested fields:

| Group | Required fields |
| --- | --- |
| Event | `schema_version`, `event_type`, `status`, `summary`, `timestamp`. |
| Runtime core | `runtime_id`, `workload_id`, `deployment_id`, `image_digest`, `rollback_category`, `source_workflow`, `evidence_links`. |
| Alarms | `alarm_snapshot` with alarm states or collection errors. |

Current AWS/GitHub details still appear under `stack`, `service`, `revision`,
`runtime`, `slo`, `github`, and `correlation`, but future runtimes should treat
those as details around the stable core rather than the cross-runtime schema.

## Rollback

Rollback paths stay separated by ownership:

- App image rollback uses the app deploy or app rollback drill path.
- Runtime data-phase rollback restores captured runtime config values.
- Infra rollback uses reviewed `Infra Plan` and `Infra Apply`.
- Schema rollback remains forward-compatible until contract; after destructive
  contract migrations it is snapshot/restore work, not a fast app rollback.
- One-off job rollback is either idempotent re-run, forward fix, or documented
  data restore. It is not an app image rollback unless the job image itself is
  the failed change.

Future runtimes should preserve these rollback categories even if their
implementation details differ.

## Toolkit Boundaries

The reusable value is the workflow and contract shape:

- workload folders under `apps/`
- shared domain/application/infrastructure packages under `packages/`
- provider-neutral config, secrets, telemetry, rollback, and evidence metadata
- runtime capabilities declared in `platform/runtime-capabilities.json`
- current AWS/ECS implementation at delivery and infrastructure edges

The repo should not grow a generic scheduler, custom deployment engine,
homegrown observability backend, private ORM, custom event broker API, or a
second runtime abstraction layer. Add a wrapper only when app code needs a
stable port; otherwise prefer the standard tool's native interface at the
owning edge.

## Current Non-Goals

This contract does not add a Kubernetes, Nomad, Azure, Google Cloud, or
second-cloud implementation. It also does not add a generic platform abstraction
layer. The next runtime target should be added only when a real workload needs
it and can be tested against the contract above.

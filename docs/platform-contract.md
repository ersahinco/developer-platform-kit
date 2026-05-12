# Platform Contract

This is the portable application contract for this repository. It describes
what a workload must provide to run on the project platform shape today, without
claiming that the current runtime is cloud-neutral.

The current implementation target is ECS, Terraform, AWS-managed dependencies,
and GitHub Actions. Future runtimes such as Kubernetes, another cloud, or lower
cost compute should satisfy this contract before the repo adds another platform
root. Do not add a second runtime only to prove portability.

## Workload Shape

Every long-running app workload should provide:

- An OCI image built from a committed Dockerfile.
- A stable app name and import package under `apps/`.
- `/health` for process liveness.
- `/ready` for dependency readiness.
- `/metrics` for Prometheus scraping.
- Structured logs that include stable correlation fields.
- Optional OTLP/HTTP traces to Tempo when tracing is enabled.

One-off and scheduled workloads should follow the same image, logging, config,
and evidence conventions. They do not need HTTP endpoints unless they expose a
service.

Current long-running workloads implementing this surface are `apps/api` and
`apps/order_event_consumer`. `apps/backfill_worker` and `apps/data_export_job`
remain one-off/scheduled workloads and should not grow HTTP endpoints just to
look like services.

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

## Observability

The portable observability baseline is Prometheus, Loki, Tempo, and Grafana.
Workloads should make these signals useful without a Grafana Cloud dependency or
a Grafana CloudWatch datasource:

- Metrics: request count, request latency, 5xx/error counts, readiness failures,
  and workload-specific outcomes.
- Logs: JSON or parseable structured lines with `stack`, `environment`,
  `service`, `container`, and relevant workload identifiers.
- Correlation: preserve `request_id` and emit `trace_id` when tracing is active.
- Delivery context: release events should include `github_run_id`, `image_tag`,
  task definition or equivalent runtime revision, status, and SLO timings.

CloudWatch remains the AWS-native alarm and managed-resource signal for the ECS
sandbox. Portable dashboards and app-owned telemetry should not require
CloudWatch queries.

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

## Rollback

Rollback paths stay separated by ownership:

- App image rollback uses the app deploy or app rollback drill path.
- Runtime data-phase rollback restores captured runtime config values.
- Infra rollback uses reviewed `Infra Plan` and `Infra Apply`.
- Schema rollback remains forward-compatible until contract; after destructive
  contract migrations it is snapshot/restore work, not a fast app rollback.

Future runtimes should preserve these rollback categories even if their
implementation details differ.

## Current Non-Goals

This contract does not add a Kubernetes, Nomad, Azure, Google Cloud, or
second-cloud implementation. It also does not add a generic platform abstraction
layer. The next runtime target should be added only when a real workload needs
it and can be tested against the contract above.

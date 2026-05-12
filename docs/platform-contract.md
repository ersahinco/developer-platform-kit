# Platform Contract

This is the portable application contract for this repository. It describes
what a workload must provide to run on the project platform shape today, without
claiming that the current runtime is cloud-neutral.

The machine-readable workload inventory lives in `platform/workloads.json` and
is enforced by `scripts/ci/validate_platform_contract.py`. Add future apps there
before adding runtime-specific infrastructure for them.

The current implementation target is ECS, Terraform, AWS-managed dependencies,
and GitHub Actions. Future runtimes such as Kubernetes, another cloud, or lower
cost compute should satisfy this contract before the repo adds another platform
root. Do not add a second runtime only to prove portability.

## Workload Shape

Every long-running app workload must provide this surface:

| Area | Contract |
| --- | --- |
| OCI image | A committed `apps/<name>/Dockerfile`, non-root runtime user, no secrets baked into layers, `PYTHONPATH`/entrypoint wiring that works from a clean image build. |
| App package | A stable app folder and import package under `apps/`; runtime wiring stays in `apps/*`, not in `packages/domain` or `packages/application`. |
| Liveness | `/health` returns `200` when the process can accept traffic, without requiring downstream dependencies. |
| Readiness | `/ready` checks required runtime dependencies and returns `503` with a structured failed check when the workload should be removed from rotation. |
| Metrics | `/metrics` exposes Prometheus text with request count, request latency, readiness/error status, and workload-specific outcome counters where useful. |
| Logs | Logs are JSON or parseable structured lines and preserve stable labels/correlation fields: `stack`, `environment`, `service`, `container`, `request_id`, and workload identifiers such as `event_id` or `job_name`. |
| Traces | OTLP/HTTP traces to Tempo are optional per workload; add them when request or job spans materially help debugging. Do not add an OpenTelemetry Collector until routing, filtering, or multi-backend export is actually needed. |
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

Release evidence events must preserve these fields, even when a future runtime
maps them to different names:

| Group | Required fields |
| --- | --- |
| Event | `schema_version`, `event_type`, `status`, `summary`, `timestamp`. |
| Stack | `stack.name`, `stack.environment`, `stack.region`, `stack.root_domain`. |
| Service | `service`. |
| Revision | `revision.image_tag`, `revision.task_definition`, `revision.previous_task_definition`, `revision.drill_task_definition`, `revision.plan_run_id`. A non-ECS runtime should use the closest immutable runtime revision in the task definition fields until a real second runtime exists. |
| Runtime | `runtime.fault_mode`, `runtime.read_mode`, `runtime.write_mode`. |
| SLO | `slo.rollback_seconds`, `slo.rollback_slo_seconds`, `slo.verify_seconds`, `slo.verify_slo_seconds`. |
| Alarms | `alarm_snapshot` with alarm states or collection errors. |
| Delivery | `github.repository`, `github.run_id`, `github.run_attempt`, `github.run_url`, `github.workflow`, `github.job`, `github.sha`, `github.ref_name`, `github.actor`. |
| Correlation | `correlation.stack`, `correlation.environment`, `correlation.service`, `correlation.image_tag`, `correlation.task_definition`, `correlation.github_run_id`. |

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

## Current Non-Goals

This contract does not add a Kubernetes, Nomad, Azure, Google Cloud, or
second-cloud implementation. It also does not add a generic platform abstraction
layer. The next runtime target should be added only when a real workload needs
it and can be tested against the contract above.

# Platform Contract

Portable workload contract for this repo.

Goal: keep the workload contract as part of the stable center of the platform so
workloads run on current and future runtime targets without leaking provider
details into app code. Use standard tools directly and keep provider details at
the platform edge.

`platform/workloads.json` is the machine-readable workload contract.
`platform/runtime-defaults.json` is the machine-readable list of blessed
runtime defaults for auth, identity, secrets, observability, policy, CI/CD, and
network behavior.
Focused pytest checks plus `make runtime-conformance` are the main proof that
declared workloads still satisfy the contract.

## Stable Center

- The workload contract is the canonical definition of workload intent.
- The platform catalog supplies reusable capabilities that realize that intent.
- Runtime targets may vary, but they must realize the contract instead of
  redefining workload meaning.

## Canonical Contract

`platform/workloads.json` owns portable workload identity and boundary
requirements:

- workload identity and kind
- target-neutral workload use cases for discovery and templates
- workload owner
- host location under `apps/`
- supported runtime targets and admitted runtime targets
- operational class
- service port declarations
- capability declarations such as database and the Dapr application APIs used
  or proven by the workload
- Dapr app identity and component mappings
- shared image package and command metadata
- portable health, metrics, traces, and idempotency expectations
- workload-facing config and secret names

It is intentionally not a deployment DSL. Add fields only when they describe a
workload boundary every relevant runtime target must understand; keep resource
counts, product wiring, rollout choreography, and provider names at the
platform edge.

## Candidate, Helper, And Catalog Guardrail

Candidate helpers and catalog artifacts may describe, check, or explain workload
boundaries. They must not create app code, redefine workload identity, own
deployment choreography, or become a hidden framework.

Use this rule for workload candidates, catalog building blocks, and examples.
These artifacts can point back to
`platform/workloads.json`, runtime defaults, and standard tool commands, but the
workload contract remains the only source of workload identity and runtime
targets remain responsible for realization.

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
or `connector` without encoding runtime details. Classification patterns stay
outside real workload metadata so operational class remains the single workload
shape axis.

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

See [Workload Observability](workload-observability.md) for the exact metric,
structured log, job event, and operator payload fields.

Job workloads must provide:

- committed OCI image
- meaningful process exit status
- safe rerun behavior or clearly bounded idempotency
- structured start, progress, success, and failure events
- the same config and secret rules as services

The current workload inventory lives in `platform/workloads.json`. Use these
views instead of copying a workload list into new docs:

```bash
make workload-capability-matrix
make workload-readiness
```

## Operational Class

| Class | Meaning |
|---|---|
| `edge-service` | user-facing or externally routed HTTP service |
| `internal-service` | long-running service without public edge ownership |
| `operator-job` | one-off task triggered manually or by CI/operator workflow |
| `scheduled-job` | recurring task triggered by a scheduler |

The current class mapping is declared per workload in `platform/workloads.json`
under `operational.class`.

Runtime details like ALB, ECS service count, EventBridge Scheduler, managed
Kubernetes manifests, or manual operator flow stay at the platform edge.

Kubernetes can be a valid future runtime realization for app hosts, batch
workloads, GPU workloads, Spark, ML/AI, or data-science workloads when a real
workload requirement and runtime owner exist. It would be another platform-edge
realization of the same contract, not a replacement for the workload contract
with Helm, CRDs, or control-plane machinery.

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

Object storage and file-output expectations follow the same rule: declare
portable config and secret names plus operator-visible evidence, then let the
runtime target choose S3, local volumes, or another owned implementation.

External systems follow a bounded dependency contract during admission. A
candidate records the dependency kind, purpose, direction, owner, declared
config and secret names, and evidence expectation. Provider resource IDs,
endpoints, credential values, and provisioning choreography remain at the
platform edge. This contract and its catalog entry may incubate before broad
adoption, but active runtime admission still requires reviewed realization and
operator ownership.

## Dapr Application APIs

Dapr is the core app-facing distributed-systems boundary. A workload declares
its Dapr app identity and the building-block scope it uses. Application teams
consume Dapr APIs; the platform owns component implementation, scoping,
resiliency, security, telemetry, and runtime delivery.

Current proven scopes:

- `service-invocation`: local booking service identity and invocation with
  scoped timeout, retry, and circuit breaker
- `pubsub`: CloudEvents and durable outbox handoff, backed locally by Redis and
  in the reviewed AWS runtime by SNS/SQS

Application code may know Dapr app ids, API contracts, pub/sub names, topics,
CloudEvents, and outbox semantics. It must not know whether runtime transport
is SNS/SQS, Redis, Kafka, Azure Service Bus, GCP Pub/Sub, or another component.
The database outbox remains the durable event handoff, and database constraints
remain the source of truth for transactional invariants. Retry, dead-letter,
idempotency, and failure behavior stay explicit.

Additional Dapr building blocks may incubate before scale through an owned
workload proof with component mapping, conformance, evidence, failure mode, and
operational ownership.

## Auth And Policy

Authn/authz is a boundary requirement, not a per-workload product choice.

- Workloads declare edge auth intent such as `edge.auth_mode` only when it is
  part of their external contract.
- Application code owns business authorization unless a runtime-owned policy
  capability exists.
- Runtime defaults document current auth, identity, secrets, CI/CD, network,
  observability, and policy choices.
- Repository policy checks protect contract shape; products such as Okta, Kong,
  OPA, Datadog, or Splunk stay out of workload metadata unless business
  behavior truly depends on them.

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

Scheduling is represented by workload class and trigger intent. A
`scheduled-job` declares the portable workload shape and evidence; EventBridge,
cron, Kubernetes CronJob, or another scheduler remains runtime-target
realization.

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

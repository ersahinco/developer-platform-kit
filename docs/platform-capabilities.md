# Platform Capabilities

Current capability inventory for the platform monorepo stable center and its
runtime realizations.

Use:

- [Platform Contract](platform-contract.md) for workload-facing rules
- [Architecture](architecture.md) for placement and ownership
- [Proof Ladder](proof-ladder.md) for the static-to-local-to-cloud evidence path

Start with these operator views:

```bash
make monorepo-capability-profile
make monorepo-capability-profile-md
make monorepo-capability-profile-check
make workload-readiness
make capability-implementation-matrix
make runtime-defaults
```

Use `make help` or the runtime docs when you need the narrower inventory,
candidate, or cloud-wiring views. `monorepo-capability-profile` is the compact
machine-readable view that ties GitHub Actions lanes, workload contract usage,
app-facing concerns, and runtime capability realization together. The matching
Markdown view is for humans, and the check target fails when required delivery
lanes or runtime capabilities disappear. `app-build.yml` uploads both views as
the `monorepo-capability-profile-<run-id>` validation artifact.

## Capability Maturity

Capability maturity is explicit on each active runtime capability row in
`platform/platform-inventory.json`. Runtime-target maturity lives with the
active runtime defaults in `platform/runtime-defaults.json`. Those active
inventories allow only:

| Maturity | Meaning |
|---|---|
| `active-local-proof` | Active local proof capability or runtime; useful for developer validation without production admission |
| `active-production-runtime` | Reviewed production runtime capability with owner, delivery path, evidence, failure mode, and runbook |

Current local runtime targets are `active-local-proof`. `aws-ecs` is the
current `active-production-runtime`. Incubating capabilities stay in bounded
admission candidates, catalog entries, and documentation until they pass the
admission rule below; they do not become rows in the active inventories.

Default auth, identity, secrets, observability, network, policy, and CI/CD
capabilities live in `platform/runtime-defaults.json`. `platform/platform-inventory.json`
keeps only non-default capability evidence such as local rollout proof, Dapr
proof, database, eventing, jobs, object storage, tracing, and release evidence.

## Capability Map

| Capability | Workload-facing contract | Current owner |
|---|---|---|
| HTTP service edge | `/health`, `/ready`, `/metrics`, structured logs, immutable image rollout | `apps/api`, `platform/workloads.json`, `infra/app/edge.tf`, workflows |
| Internal async service | long-running internal service shape, direct DB access, Dapr-backed event handling | `apps/event_consumer`, `platform/workloads.json`, `infra/app/workload_jobs.tf`, `infra/app/messaging.tf` |
| Dapr application APIs | app identity, service invocation, pub/sub, CloudEvents, component scoping, resiliency, and runtime-owned implementation | `platform/concerns/dapr/`, `platform/workloads.json`, `packages/infrastructure/dapr` |
| Operator job execution | one-off job shape, rerun expectation, structured completion events, payload artifacts | `apps/backfill_worker`, `apps/operational_snapshot_job`, `apps/integration_check_job`, workflows, `infra/app/workload_jobs.tf` |
| Scheduled job execution | recurring job shape, scheduler-driven run, export success expectations | `apps/data_export_job`, `infra/app/workload_jobs.tf`, `infra/app/object_storage.tf` |
| Database rollout safety | read/write mode switches, backfill, contract migration flow | `db/`, `apps/api`, `packages/application`, runbooks |
| Local observability | Prometheus, Loki, Tempo, Grafana, Promtail | `platform/concerns/observability/`, `compose.yaml` |
| Cloud observability signals | CloudWatch logs, CloudWatch alarms, optional ADOT sidecar | `infra/app`, `scripts/observability/`, runbooks |
| Release evidence | portable release event, artifact upload, optional Loki push | workflows, `scripts/observability/release_event.py` |
| Incident evidence | portable bundle with ECS, alarms, release context, query hints | `scripts/observability/incident_evidence_bundle.py` |
| Operational snapshot | read-only job that emits runtime mode and data posture for release or incident context | `apps/operational_snapshot_job`, `operational-snapshot.yml`, `make operational-snapshot`, `make operational-snapshot-cloud` |
| Integration checks | configured HTTP checks that emit a local operator evidence payload | `apps/integration_check_job`, `make integration-check` |
| Booking consistency proof | database-enforced slot uniqueness with a concurrent one-winner integration test | `apps/booking_api`, `packages/application/booking.py`, `packages/infrastructure/db/bookings.py` |
| Late-event projection proof | deterministic deduplication, late-arrival classification, projection rebuild, and artifact hashes | `apps/lake_orders_ingest_job` |
| MLOps artifact proof | training-data lineage, bounded evaluation, drift summary, promotion decision, artifact compatibility, and model identity at inference | `apps/churn_model_train_job`, `apps/churn_prediction_api` |
| Runtime conformance | external proof that workloads satisfy the declared contract | `platform/runtime-conformance.json`, `tests/runtime/`, `make runtime-conformance` |
| Network connectivity | declared ports, local service names, public edge ingress, private placement, private dependency connectivity | `compose.yaml`, `platform/runtime-conformance.json`, `infra/platform/network.tf`, `infra/app/edge.tf`, `infra/app/compute_ecs.tf` |
| Local Kubernetes rollout proof | API Deployment rollout, probe verification, rollback, and local evidence without production Kubernetes machinery | `infra/local-kubernetes/`, `scripts/platform/local_kubernetes_proof.py`, `make local-kubernetes-rollout-proof` |
| Local Kubernetes Dapr proof | event-consumer sidecar, Redis-backed local pub/sub, API-created order event, CloudEvent delivery, and consume-log evidence inside the evidence drill | `infra/local-kubernetes/`, `scripts/platform/local_kubernetes_proof.py`, `make local-kubernetes-evidence-drill` |
| Local Kubernetes evidence drill | repeatable kind validation, Dapr proof, runtime logs, endpoints, events, admission report, JSON evidence, and cleanup | `Makefile`, `scripts/platform/local_kubernetes_proof.py`, `make local-kubernetes-evidence-drill` |
| CI/CD delivery | local validation, immutable image tags, separated build/deploy, reviewed plan/apply, workflow run IDs, release evidence | `Makefile`, `.github/workflows/`, `infra/platform/github_actions.tf`, `scripts/observability/release_event.py` |
| Observability routing | standard metrics/logs/traces emitted by workloads and routed by the runtime edge | `platform/concerns/observability/`, `compose.yaml`, `infra/app/app_log_groups.tf`, `infra/app/observability.tf`, `scripts/observability/` |
| Authz policy | app-local business authorization by default plus repo/runtime metadata policy checks | `platform/concerns/policy/`, `platform/runtime-defaults.json`, `tests/contracts/test_policy_contract.py` |

## Self-Service Boundary

The self-service product shape for this repo is workload and capability
admission on existing infrastructure. Developers request contract-level
outcomes; platform engineering realizes them through the current runtime target
and catalog surfaces.

Requests may arrive in AWS-shaped language such as ECS, IAM, subnets, buckets,
queues, or schedulers. Treat those as runtime context, not the product surface.
Admission is approved only after the request is translated into a
contract-governed workload or bounded capability that the platform catalog can
realize at the platform edge.

For separate application repositories, app teams own application code and their
copy of the CI lane. This platform repo owns the workload contract shape,
runtime realization, catalog entries, policy checks, and evidence expectations.

Good admission requests:

- run or promote a contract-governed workload
- give a workload or job object output through a declared artifact sink
- subscribe or publish through the Dapr pub/sub boundary for a real async need
- schedule a declared job or add one-off operator execution
- promote a local workload to `aws-ecs` after local proof

Non-goals:

- arbitrary AWS resource vending
- per-team Terraform surfaces
- raw ECS, IAM, subnet, queue, rule, bucket, or database product fields in
  `platform/workloads.json`
- a portal, generator, control plane, Helm/CRD layer, or provider-neutral
  infrastructure module without a bounded capability outcome and proof path

Use the GitHub issue form `Workload or capability admission` as the intake
surface and `workload-capability-admission.md` as the matching implementation
PR template. Use `make workload-readiness` and `make workload-readiness-check`
for current workloads. Validate a draft before adding it with
`WORKLOAD_CANDIDATE=/path/to/workload.json make workload-admission-check`.

Capabilities may incubate before demand reaches scale. Keep that work bounded:
name an owner, validate a concrete candidate, add contract and catalog tests,
identify the implementation and evidence path, and label it non-production
until runtime admission is reviewed. The bounded dependency candidate under
`platform/admission/candidates/` is the reference shape for identity, DNS,
external API, database, SaaS, or partner-system access without leaking provider
resource wiring into workload identity.

## Dapr Application Boundary

Dapr sits at the core of distributed application building in this toolkit.
App teams use stable building-block APIs while platform engineering owns
component implementation, scoping, resiliency, security policy, telemetry,
and runtime delivery. This follows
[Dapr's platform-engineering model](https://dapr.io/platform-engineering/):
expose simple application interfaces while keeping infrastructure choices and
governance at the platform edge.

Current proofs:

- pub/sub: CloudEvents and durable database outbox, backed locally by Redis and
  in the reviewed production runtime by SNS/SQS
- service invocation: the local booking workload is invoked through its Dapr
  app identity with scoped timeout, retry, and circuit-breaker policy

Choose the next Dapr experiment from a concrete failure mode in an existing
workload, such as orchestration and recovery across churn training, evaluation,
and promotion. Add only the building block that proof needs, with a component
mapping, contract, conformance, evidence, failure mode, and runbook.
Dapr coordinates distributed behavior; domain policy, durable outbox handoff,
and database consistency invariants remain explicit in the application and
data model.

## Runtime Targets

Current local runtime targets: `local-compose`, `local-kubernetes`.
Current reviewed production runtime target: `aws-ecs`.
Future provider-edge options may have bounded admission and catalog proofs
before broad adoption. They remain outside active runtime defaults until a
concrete proof workload and runtime ownership are clear.

The runtime-family vocabulary and ownership implications live in
[Runtime Toolkit](runtime-toolkit.md). This capability inventory names only
active targets and bounded incubation paths; it does not maintain a catalog of
possible runtime products.

Rule:

- keep provider details visible at the platform edge
- keep the workload contract portable
- keep the platform catalog recognizable across runtime targets
- do not turn the contract into deployment choreography
- keep local fast enough to stay the default development loop

Future runtime replacements should plug in at the seams named below and in the
replacement seams in `platform/platform-inventory.json`. Use
`make capability-implementation-matrix` and `make runtime-defaults` for
executable views.

Use `make workload-readiness` and `make workload-readiness-cloud` to inspect
declared workload proof surfaces. Use `make local-compose-live-proof` only
when you need the isolated live Compose drill for token auth, health,
readiness, metrics, logs, and local observability. New runtime capabilities stay
out of machine defaults until the owner, conformance, evidence, failure mode,
and runbook exist.

## Adapter Seams

Portable workload behavior should survive runtime-target changes by keeping the
current realization behind explicit adapter seams:

- database behavior: PostgreSQL-compatible contract in `packages/infrastructure/db/` and runtime-specific data resources in `infra/app/database.tf`
- pub/sub behavior: Dapr-facing adapter in `packages/infrastructure/dapr/` and current broker backing resources in `infra/app/messaging.tf`
- object-output behavior: infrastructure adapters in `packages/infrastructure/` and current storage realization in `infra/app/object_storage.tf`
- secrets and runtime wiring: declared workload config in `platform/workloads.json` and current injection in `infra/app/workload_inventory.tf`
- local runtime behavior: Compose plus `platform/runtime-conformance.json` proves the contract without depending on cloud resources
- local Kubernetes behavior: kind plus static manifests prove selected network, storage, probe, job, service identity, config, and secret boundaries

Rule: add or swap adapters and runtime-target realization code before changing
the workload contract or application core.

## Ownership Rules

- add workload need to `platform/workloads.json`
- add shared platform capability to `platform/concerns/` or `infra/catalog/`
- add provider/runtime implementation to `infra/`, workflows, or scripts
- add reusable adapter logic only after repetition is proven

If a capability belongs to all runtimes, prefer the contract. If it exists only
because the current AWS runtime implements it, keep it out of the contract and
record it here or in runtime-facing docs.

Workload placement rule:

- put real workload hosts in `apps/`, even when they are local-only
- keep `examples/` for teaching, demo, and reference-only samples
- require a declared workload owner before cloud runtime admission
- admit a workload to `aws-ecs` only after reviewed runtime realization and delivery ownership exist

## Admission Rule

- incubate a capability before broad demand only with an owner, concrete proof, contract, tests, evidence path, and honest maturity
- promote a capability to an active runtime only when it has local proof, runtime realization, delivery path, and owner
- decide first: portable contract, current capability inventory, or AWS runtime only
- do not add provider-neutral abstraction layers speculatively

## Not Yet Platform Capabilities

- unowned Dapr building blocks without component mapping, workload proof,
  conformance, and operational evidence
- generic analytics orchestration or transformation platforms
- generic open-source data-tool stacks presented as shared platform defaults;
  specialized tools may stay inside an owned experimental workload that proves
  a named behavior
- hosted Grafana/Loki/Tempo/Prometheus runtime modules
- a runtime target added without a concrete workload need and owner
- generic provider-neutral infrastructure modules

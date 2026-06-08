# Platform Capabilities

Current capability inventory for the platform monorepo stable center and its
runtime realizations.

Use:

- [Platform Contract](platform-contract.md) for workload-facing rules
- [Architecture](architecture.md) for placement and ownership

Start with these operator views:

```bash
make capability-implementation-matrix
make capability-proof-local
make capability-proof-local-live
make enterprise-runtime-fit-check
```

Use `make help` or the runtime docs when you need the narrower inventory,
candidate, adapter-seam, or cloud-wiring views.

## Capability Maturity

Capability and runtime-target maturity is explicit in
`platform/platform-inventory.json`:

| Maturity | Meaning |
|---|---|
| `candidate` | Known possible capability or runtime; not active until owner, config surface, conformance, evidence, failure mode, and runbook exist |
| `active-local-proof` | Active local proof capability or runtime; useful for developer validation without production admission |
| `active-production-runtime` | Reviewed production runtime capability with owner, delivery path, evidence, failure mode, and runbook |
| `deprecated` | Retired or being removed; kept only while workloads migrate away |

Current local runtime targets are `active-local-proof`. `aws-ecs` is the
current `active-production-runtime`. Enterprise tools and future runtime
targets stay `candidate` until they pass the admission rule below.

## Capability Map

| Capability | Workload-facing contract | Current owner |
|---|---|---|
| HTTP service edge | `/health`, `/ready`, `/metrics`, structured logs, immutable image rollout | `apps/api`, `platform/workloads.json`, `infra/app/edge.tf`, workflows |
| Internal async service | long-running internal service shape, direct DB access, Dapr-backed event handling | `apps/event_consumer`, `platform/workloads.json`, `infra/app/workload_jobs.tf`, `infra/app/messaging.tf` |
| Dapr pub/sub | app id, pub/sub name, topic, resiliency semantics | `platform/concerns/dapr/`, `platform/workloads.json`, `packages/infrastructure/dapr` |
| Operator job execution | one-off job shape, rerun expectation, structured completion events, payload artifacts | `apps/backfill_worker`, `apps/operational_snapshot_job`, `apps/integration_check_job`, workflows, `infra/app/workload_jobs.tf` |
| Scheduled job execution | recurring job shape, scheduler-driven run, export success expectations | `apps/data_export_job`, `infra/app/workload_jobs.tf`, `infra/app/object_storage.tf` |
| Database rollout safety | read/write mode switches, backfill, contract migration flow | `db/`, `apps/api`, `packages/application`, runbooks |
| Local observability | Prometheus, Loki, Tempo, Grafana, Promtail | `platform/concerns/observability/`, `compose.yaml` |
| Cloud observability signals | CloudWatch logs, CloudWatch alarms, optional ADOT sidecar | `infra/app`, `scripts/observability/`, runbooks |
| Release evidence | portable release event, artifact upload, optional Loki push | workflows, `scripts/observability/release_event.py` |
| Incident evidence | portable bundle with ECS, alarms, release context, query hints | `scripts/observability/incident_evidence_bundle.py` |
| Operational snapshot | read-only job that emits runtime mode and data posture for release or incident context | `apps/operational_snapshot_job`, `operational-snapshot.yml`, `make operational-snapshot`, `make operational-snapshot-cloud` |
| Integration checks | configured HTTP checks that emit a local operator evidence payload | `apps/integration_check_job`, `make integration-check` |
| Runtime conformance | external proof that workloads satisfy the declared contract | `platform/runtime-conformance.json`, `tests/runtime/`, `make runtime-conformance` |
| Network connectivity | declared ports, local service names, public edge ingress, private placement, private dependency connectivity | `compose.yaml`, `platform/runtime-conformance.json`, `infra/platform/network.tf`, `infra/app/edge.tf`, `infra/app/compute_ecs.tf` |
| CI/CD delivery | local validation, immutable image tags, separated build/deploy, reviewed plan/apply, workflow run IDs, release evidence | `Makefile`, `.github/workflows/`, `infra/platform/github_actions.tf`, `scripts/observability/release_event.py` |
| Observability routing | standard metrics/logs/traces emitted by workloads and routed by the runtime edge | `platform/concerns/observability/`, `compose.yaml`, `infra/app/app_log_groups.tf`, `infra/app/observability.tf`, `scripts/observability/` |
| Authz policy | app-local business authorization by default plus repo/runtime metadata policy checks | `platform/concerns/policy/`, `platform/runtime-defaults.json`, `tests/contracts/test_policy_contract.py` |

## Dapr Boundary

Dapr is useful when an app interacts with multiple systems that run at
different cadences. Treat Dapr building blocks as app-facing boundary
vocabulary, not as a platform shopping list.

Current adopted block:

- pub/sub: app-facing eventing boundary with CloudEvents and durable database
  outbox; current production backing is SNS/SQS.

Good future candidates when real workloads need them:

- service invocation for service-to-service calls with consistent identity,
  resiliency, and telemetry expectations
- secrets and configuration as portable boundary vocabulary, even when the
  runtime realization is ECS, Kubernetes, or another secret/config provider
- resiliency policies for retries, timeouts, and circuit breaking across
  cross-system calls
- jobs, workflows, state, bindings, actors, locks, cryptography, or
  conversation only when a workload has a concrete need and owner

Adopt a new Dapr block only with owner, config surface, conformance, evidence,
failure mode, and runbook. Keep business behavior in the app and runtime
realization at the platform edge.

## Runtime Targets

Current local runtime targets: `local-compose`, `local-kubernetes`.
Current reviewed production runtime target: `aws-ecs`.
Future provider-edge options stay horizon guidance only until a real workload
needs them and runtime ownership is clear.

Runtime families:

- local proof runtimes: `local-compose` for fastest feedback; `local-kubernetes`
  for richer local network, storage, compute, probes, jobs, sidecars, service
  identity, or policy proof
- managed app runtimes: `aws-ecs` today; future ECS/Fargate variants, Lambda,
  Azure Functions, Cloud Run, Azure Container Apps, or similar managed hosts
  when they preserve the workload contract and evidence
- owned substrate runtimes: EC2 or VM fleets, on-prem servers, self-managed
  Kubernetes, and managed Kubernetes when the platform owns ingress,
  node/runtime posture, storage classes, identity mapping, policy,
  observability, upgrades, and runbooks

Local Kubernetes is an active proof runtime. Managed or self-managed production
Kubernetes remains a future runtime realization for app-host, batch, GPU, Spark,
ML/AI, or data-science workloads only when those needs are real and owned. It
must realize the same workload contract at the platform edge; do not add Helm,
CRD, or control-plane machinery just to prove portability.

Rule:

- keep provider details visible at the platform edge
- keep the workload contract portable
- keep the platform catalog recognizable across runtime targets
- do not turn the contract into deployment choreography
- keep local fast enough to stay the default development loop

Future runtime replacements should plug in at the seams shown by
`make capability-implementation-matrix`, `make candidate-capability-matrix`, and
`make adapter-seam-matrix`.

Use `make capability-proof-local` to see current local evidence behind each
active runtime capability. Use `make capability-proof-cloud` to inspect AWS
wiring evidence; it is not a live deployed-cloud probe. Use
`make capability-proof-local-live` for an isolated live local drill that starts
Compose, enables token auth, probes runtime behavior, and cleans up. Use
`make enterprise-runtime-fit-check` to see why candidate enterprise capabilities
remain candidate-only.

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

- standardize a new capability only when a real workload needs it
- admit a capability only when it has contract shape, local proof, runtime realization, delivery path, and owner
- decide first: portable contract, current capability inventory, or AWS runtime only
- do not add provider-neutral abstraction layers speculatively

## Not Yet Platform Capabilities

- Dapr state store, bindings, workflows, actors, or secrets
- analytics orchestration or data transformation stacks
- open-source data load / DuckDB / dbt stacks as automatic AWS-admitted platform workloads
- hosted Grafana/Loki/Tempo/Prometheus runtime modules
- a runtime target added without a concrete workload need and owner
- generic provider-neutral infrastructure modules

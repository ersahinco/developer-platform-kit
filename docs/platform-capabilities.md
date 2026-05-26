# Platform Capabilities

Current capability inventory for the platform monorepo stable center and its
runtime realizations.

Use:

- [Platform Contract](platform-contract.md) for workload-facing rules
- [Architecture](architecture.md) for placement and ownership

Inspect the current implementation directly:

```bash
make workload-capability-matrix
make capability-implementation-matrix
make adapter-seam-matrix
```

## Capability Map

| Capability | Workload-facing contract | Current owner |
|---|---|---|
| HTTP service edge | `/health`, `/ready`, `/metrics`, structured logs, immutable image rollout | `apps/api`, `platform/workloads.json`, `infra/app/edge.tf`, workflows |
| Internal async service | long-running internal service shape, direct DB access, Dapr-backed event handling | `apps/event_consumer`, `platform/workloads.json`, `infra/app/workload_jobs.tf`, `infra/app/messaging.tf` |
| Dapr pub/sub | app id, pub/sub name, topic, resiliency semantics | `platform/concerns/dapr/`, `platform/workloads.json`, `packages/infrastructure/dapr` |
| Operator job execution | one-off job shape, rerun expectation, structured completion events | `apps/backfill_worker`, workflows, `infra/app/workload_jobs.tf` |
| Scheduled job execution | recurring job shape, scheduler-driven run, export success expectations | `apps/data_export_job`, `infra/app/workload_jobs.tf`, `infra/app/object_storage.tf` |
| Database rollout safety | read/write mode switches, backfill, contract migration flow | `db/`, `apps/api`, `packages/application`, runbooks |
| Local observability | Prometheus, Loki, Tempo, Grafana, Promtail | `platform/concerns/observability/`, `compose.yaml` |
| Cloud observability signals | CloudWatch logs, CloudWatch alarms, optional ADOT sidecar | `infra/app`, `scripts/observability/`, runbooks |
| Release evidence | portable release event, artifact upload, optional Loki push | workflows, `scripts/observability/release_event.py` |
| Incident evidence | portable bundle with ECS, alarms, release context, query hints | `scripts/observability/incident_evidence_bundle.py` |
| Runtime conformance | external proof that workloads satisfy the declared contract | `platform/runtime-conformance.json`, `tests/runtime/`, `make runtime-conformance` |

## Runtime Targets

Current local runtime target: `local-compose`.
Current reviewed production runtime target: `aws-ecs`.
Future hybrid runtime edge: managed service providers when a workload needs
managed global database, DNS, edge, identity, or storage capabilities.

Rule:

- keep provider details visible at the platform edge
- keep the workload contract portable
- keep the platform catalog recognizable across runtime targets
- do not turn the contract into deployment choreography
- keep local fast enough to stay the default development loop

Future runtime replacements should plug in at the seams shown by
`make capability-implementation-matrix` and `make adapter-seam-matrix`.

## Adapter Seams

Portable workload behavior should survive runtime-target changes by keeping the
current realization behind explicit adapter seams:

- database behavior: PostgreSQL-compatible contract in `packages/infrastructure/db/` and runtime-specific data resources in `infra/app/database.tf`
- pub/sub behavior: Dapr-facing adapter in `packages/infrastructure/dapr/` and current broker backing resources in `infra/app/messaging.tf`
- object-output behavior: infrastructure adapters in `packages/infrastructure/` and current storage realization in `infra/app/object_storage.tf`
- secrets and runtime wiring: declared workload config in `platform/workloads.json` and current injection in `infra/app/workload_inventory.tf`
- local runtime behavior: Compose plus `platform/runtime-conformance.json` proves the contract without depending on cloud resources

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

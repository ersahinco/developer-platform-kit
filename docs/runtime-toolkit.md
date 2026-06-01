# Runtime Toolkit

Use this doc when evaluating or adding a runtime target such as local Compose,
AWS/ECS, or a future provider-edge integration backed by a real workload need.
Goal: prove the runtime can satisfy the workload contract without moving
provider assumptions into app code.

Use with:

- [Platform Contract](platform-contract.md): portable workload rules
- [Architecture](architecture.md): repo and ownership boundaries
- [Platform Capabilities](platform-capabilities.md): current capability map

`platform/workloads.json` is the machine-readable workload contract.
`platform/runtime-conformance.json` is the local/CI runtime proof fixture.
`make runtime-conformance` is the main executable proof.

The stable center stays the same:

- the workload contract defines workload intent
- the platform catalog provides reusable capabilities
- runtime targets realize the contract at the platform edge

## Entry Criteria

- There is a concrete reason: cost, reliability, capability, or region/account need.
- Local development remains fast enough to be the default inner loop.
- `packages/domain` and `packages/application` do not need provider imports or runtime-specific knowledge.
- Existing workloads keep the same portable contract unless every runtime should support new behavior.

Do not add a runtime target just to prove portability.

For now, AWS is the only reviewed cloud runtime in this repo. Managed database,
DNS, edge, identity, or storage providers stay on the horizon until a workload
has a concrete need and clear runtime ownership.

## Runtime Must Provide

- OCI image execution with immutable revisions and non-root users
- networking, DNS, ingress, and dependency routing
- short-lived delivery identity and least-privilege runtime identity
- secret injection without baking values into images or artifacts
- Prometheus-compatible metrics, Loki-compatible logs, and OTLP/HTTP traces when enabled
- one-off and scheduled jobs using the same image, config, secrets, and evidence shape
- immutable rollout, explicit rollback categories, and portable release evidence
- separate bootstrap/platform and app/runtime ownership

It must also preserve workload classes:

- externally routed edge services
- internal long-running services
- manually triggered operator jobs
- scheduler-triggered recurring jobs

## Current Runtime Targets

`local-compose` is the local-first runtime for fast iteration. It uses Docker
Compose, local Postgres/PgBouncer, Redis-backed Dapr pub/sub, and the OSS
observability stack to prove the workload contract before cloud deployment.

`aws-ecs` is the current reviewed production runtime. It realizes the same
contract with ECS/Fargate, ALB/WAF, RDS, SNS/SQS behind Dapr, S3, EventBridge
Scheduler, IAM, and CloudWatch.

A provider-edge integration can still be documented as a future option, but it
should not appear as an active runtime target until there is a real workload,
reviewed ownership, and delivery path.

A workload can still be real and live under `apps/` before it is admitted to a
cloud runtime. Local support through `local-compose` is a valid first runtime
target, not a reason to demote the host into `examples/`.

## AWS ECS Target

The current `aws-ecs` target is implemented through `infra/`,
`.github/workflows/`, `scripts/`, `platform/concerns/`, tests, and docs.

- AWS details stay in `infra/platform`, `infra/app`, and AWS-facing scripts.
- The portable part is the workload contract and evidence.
- `platform/workloads.json` remains the workload contract across runtime targets.
- `platform/runtime-conformance.json` stays runtime-check-specific; do not grow it into a second workload contract.

Inspection commands:

```bash
make workload-capability-matrix
make capability-implementation-matrix
make adapter-seam-matrix
```

For current AWS rollout and operator flow, use [Deployment](deployment.md).

## Portable Baseline

| Area | Status |
|---|---|
| Application core | Portable |
| Workload contract | Portable shape |
| Data and database | PostgreSQL-compatible shape |
| Local runtime | First-class contract proof |
| Observability baseline | Mostly OSS-portable |
| Incident and release evidence | Portable shape |
| Cloud runtime implementation | Intentionally AWS-specific |

## Adapter Strategy

Prefer portability through explicit adapters and replacement seams:

- keep business behavior in `packages/domain` and `packages/application`
- keep database, pub/sub, storage, and HTTP client adapters in `packages/infrastructure`
- keep runtime-target realization in `infra/`, workflows, and scripts
- use `make capability-implementation-matrix` and `make adapter-seam-matrix` to identify the current runtime and adapter seams before adding a new target

For this repo today:

- PostgreSQL behavior is the portable database contract; RDS is the current realization
- Dapr pub/sub is the app-facing eventing contract; SNS/SQS is the current realization
- workload config and secret names are portable; ECS task/env wiring is the current realization

## Current Gaps

- CI-to-Loki publishing is ready but inactive
- AWS-managed resource metrics still rely on CloudWatch at the platform edge
- no additional production runtime target is implemented yet
- infra rollback remains reviewed plan/apply, not a permanent drill workflow

## Implementation Steps

1. Document the runtime reason.
2. Add explicit `infra/` ownership boundaries and catalog parts first.
3. Implement networking, identity, secrets, ingress, observability, job, and rollout behavior at the platform edge.
4. Keep app/domain/application code unchanged unless the portable contract itself must grow.
5. Run `make runtime-conformance` and the normal workflow, docs, and Terraform checks.

## Exit Criteria

- distinct bootstrap/platform and app/runtime roots
- declared workload images pass `make runtime-conformance`
- incident and release evidence stay recognizable across deploy and rollback
- existing workload intent remains recognizable without reinvention
- provider names stay out of `packages/domain`, `packages/application`, and workload business behavior

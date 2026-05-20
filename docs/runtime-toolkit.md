# Runtime Toolkit

Use this doc when evaluating or adding a hosting runtime such as EKS, Azure,
GCP, Nomad, or cheaper compute. Goal: prove the runtime can host portable
workloads without moving provider assumptions into app code.

Use with:

- [Platform Contract](platform-contract.md): portable workload rules
- [Architecture](architecture.md): repo and ownership boundaries
- [Platform Capabilities](platform-capabilities.md): current capability map

`platform/workloads.json` is the application spec.
`platform/runtime-conformance.json` is the local/CI fixture.
`make runtime-conformance` is the main executable proof.

## Entry Criteria

- There is a concrete reason: cost, reliability, capability, or region/account need.
- `packages/domain` and `packages/application` do not need provider imports or runtime-specific knowledge.
- Existing workloads keep the same portable contract unless every runtime should support new behavior.

Do not add a second runtime just to prove portability.

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

## Current AWS ECS Target

The current `aws-ecs` target is implemented through `infra/`,
`.github/workflows/`, `scripts/`, `compose.yaml`, `platform/concerns/`, tests,
and docs.

- AWS details stay in `infra/platform`, `infra/app`, and AWS-facing scripts.
- The portable part is the workload contract and evidence.
- `platform/workloads.json` remains the workload spec with one runtime.
- `platform/runtime-conformance.json` stays runtime-check-specific; do not grow it into a second app spec.

Inspection commands:

```bash
make workload-capability-matrix
make capability-implementation-matrix
```

For current AWS rollout and operator flow, use [Deployment](deployment.md).

## Portable Baseline

| Area | Status |
|---|---|
| Application core | Portable |
| Workload contract | Portable shape |
| Data and database | PostgreSQL-compatible shape |
| Local runtime | Portable |
| Observability baseline | Mostly OSS-portable |
| Incident and release evidence | Portable shape |
| Cloud runtime implementation | Intentionally AWS-specific |

## Current Gaps

- CI-to-Loki publishing is ready but inactive
- AWS-managed resource metrics still rely on CloudWatch at the platform edge
- no second runtime exists yet
- infra rollback remains reviewed plan/apply, not a permanent drill workflow

## Implementation Steps

1. Document the runtime reason.
2. Add explicit `infra/` ownership boundaries first.
3. Implement networking, identity, secrets, ingress, observability, job, and rollout behavior at the platform edge.
4. Keep app/domain/application code unchanged unless the portable contract itself must grow.
5. Run `make runtime-conformance` and the normal workflow, docs, and Terraform checks.

## Exit Criteria

- distinct bootstrap/platform and app/runtime roots
- declared workload images pass `make runtime-conformance`
- incident and release evidence stay recognizable across deploy and rollback
- provider names stay out of `packages/domain`, `packages/application`, and workload business behavior

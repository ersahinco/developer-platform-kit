# Runtime Toolkit

Use this document when evaluating or adding a hosting runtime such as EKS,
Azure, GCP, Nomad, or cheaper compute. The goal is not multi-cloud ceremony.
The goal is to prove that a real runtime can host the existing portable
workloads without moving provider assumptions into app code.

Use this doc together with:

- [Platform Contract](platform-contract.md) for portable workload expectations
- [Architecture](architecture.md) for repo and ownership boundaries
- [Platform Capabilities](platform-capabilities.md) for the current capability
  surface

`platform/workloads.json` is the temporary application specification.
`platform/runtime-conformance.json` is the local/CI runtime fixture.
`make runtime-conformance` is the main executable proof that declared workloads
still satisfy the contract from the outside.

## Entry Criteria

- There is a concrete operating reason: cost, reliability, capability, or
  region/account need.
- `packages/domain` and `packages/application` do not need provider imports or
  runtime-specific knowledge.
- Existing workloads keep the same portable contract unless every runtime should
  support the same new behavior.

Do not add a second runtime just to prove portability.

## Runtime Must Provide

Before a runtime is called supported, it must provide:

- OCI image execution with immutable revisions and non-root runtime users
- Networking, DNS, ingress, and dependency routing
- Short-lived delivery identity and least-privilege runtime identity
- Secret injection without baking values into images or artifacts
- Prometheus-compatible metrics, Loki-compatible logs, and OTLP/HTTP traces
  when enabled
- One-off and scheduled jobs using the same image, config, secrets, and
  evidence conventions
- Immutable rollout, explicit rollback categories, and portable release
  evidence
- Separate bootstrap/platform and app/runtime infrastructure ownership

The runtime must also preserve declared workload operational classes:

- externally routed edge services
- internal long-running services
- manually triggered operator jobs
- scheduler-triggered recurring jobs

## Current AWS ECS Target

The current `aws-ecs` target is implemented through `infra/`,
`.github/workflows/`, `scripts/`, `compose.yaml`, `platform/concerns/`, tests,
and docs.

- AWS details stay in `infra/platform`, `infra/app`, and AWS-facing scripts.
- The portable part is the workload contract and evidence shape.
- `platform/workloads.json` remains the workload specification while there is
  one runtime.
- `platform/runtime-conformance.json` stays runtime-check-specific and should
  not grow into a second application spec.

For current AWS rollout and operator flow, use [Deployment](deployment.md)
instead of this document.

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

- CI-to-Loki publishing is ready but not active.
- AWS-managed resource metrics still rely on CloudWatch at the platform edge.
- No second runtime exists yet.
- Infra rollback remains reviewed plan/apply, not a permanent drill workflow.

## Implementation Steps

1. Document the reason for the runtime.
2. Add explicit `infra/` ownership boundaries first.
3. Implement networking, identity, secrets, ingress, observability, job, and
   rollout behavior at the platform edge.
4. Keep app/domain/application code unchanged unless the portable contract
   itself needs to grow.
5. Run `make runtime-conformance` and the normal workflow/docs/Terraform checks.

## Exit Criteria

- The runtime has distinct bootstrap/platform and app/runtime ownership roots.
- Declared workload images pass `make runtime-conformance`.
- Incident and release evidence remain recognizable across deploy and rollback.
- Provider names stay out of `packages/domain`, `packages/application`, and
  workload business behavior.

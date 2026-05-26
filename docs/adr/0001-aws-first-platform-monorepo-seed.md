# ADR 0001: AWS-First Platform Monorepo Seed

## Status

Accepted on 2026-05-18

## Decision

Treat this repository as a platform monorepo seed with three explicit layers:

- infrastructure catalog
- platform concerns
- workload hosts plus examples

Keep AWS as the only supported cloud implementation for now. Keep portability
at the boundary between workloads and platform/runtime concerns rather than
introducing a provider-neutral framework or speculative multi-cloud layer.

## Why

- The repo already has strong workload and package boundaries.
- The current AWS/ECS runtime is real enough to teach delivery, rollback,
  observability, and runtime ownership without extra scaffolding.
- A second runtime, generic abstraction layer, or Kubernetes control plane
  would add cognitive load without solving a current problem.

## Consequences

- `infra/platform` and `infra/app` remain deployable assembly roots.
- `infra/catalog/aws` becomes the extraction point for reusable AWS building
  blocks only when real reuse appears.
- `platform/concerns` becomes the home for Dapr, observability, security,
  policy, and networking concerns.
- `apps/*` remain the home for contract-governed workload hosts; teaching and
  demo samples belong under `examples/`.
- `platform/workloads.json` remains the canonical workload contract for now.

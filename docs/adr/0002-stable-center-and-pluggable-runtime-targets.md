# ADR 0002: Stable Center And Pluggable Runtime Targets

## Status

Accepted on 2026-05-21

## Decision

Treat the workload contract and platform catalog as the stable center of the
platform monorepo.

Keep:

- `platform/workloads.json` as the canonical workload contract
- `platform/concerns/` and `infra/catalog/` as the reusable platform catalog surface
- `infra/platform` and `infra/app` as the current AWS runtime realization roots
- Terraform/OpenTofu as the default provisioning engine
- GitHub Actions as the default delivery engine

Allow managed Kubernetes as a future runtime target, but do not require the
platform itself to become a Kubernetes-native control plane.

## Why

- The repo needs one durable center for workload meaning, ownership, and
  portability rules as more workload types appear.
- The existing AWS/ECS realization is useful and should be preserved rather
  than renamed or replaced prematurely.
- Managed Kubernetes may become a valid runtime target for some workloads
  without implying that ArgoCD, Crossplane, or a Kubernetes-hosted platform
  control plane must become core platform dependencies.
- The catalog should grow through explicit runtime-target seams rather than
  speculative cross-cloud abstractions.

## Consequences

- Runtime targets are additive realizations at the platform edge, not new
  sources of workload meaning.
- Future runtime-target catalog modules belong under
  `infra/catalog/<runtime-target>/`.
- `infra/catalog/managed-kubernetes/` is reserved for future reusable
  managed-Kubernetes modules when a real workload needs them.
- `platform/runtime-conformance.json` remains fixture data only; it must not
  become a second workload specification.
- Backstage remains optional as a portal and catalog UX layer over the stable
  center, not the source of truth.
- ArgoCD is only relevant if Kubernetes becomes a repeated application runtime,
  not as a universal delivery requirement.
- Crossplane and Kubernetes-native platform-control-plane assumptions remain out
  of scope for now.

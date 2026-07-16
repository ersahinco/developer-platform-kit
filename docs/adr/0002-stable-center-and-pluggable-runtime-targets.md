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

Allow future provider-edge integrations or additional runtime targets to
incubate before broad demand through bounded candidates, catalog entries, and
tests. Promote them into active defaults only with a concrete proof workload,
owner, conformance, evidence, and delivery path, without turning the platform
into a speculative multi-runtime control plane.

## Why

- The repo needs one durable center for workload meaning, ownership, and
  portability rules as more workload types appear.
- The existing AWS/ECS realization is useful and should be preserved rather
  than renamed or replaced prematurely.
- Some workloads may eventually need managed provider edges such as Postgres,
  DNS, storage, or identity integrations without changing the stable center.
- The catalog should grow through explicit runtime-target seams rather than
  speculative cross-cloud abstractions.

## Consequences

- Runtime targets are additive realizations at the platform edge, not new
  sources of workload meaning.
- Future runtime-target catalog modules belong under
  `infra/catalog/<runtime-target>/`.
- New runtime-target catalog branches may incubate with a concrete proof,
  contract input, tests, evidence path, honest maturity, and clear owner;
  runtime defaults and deploy roots require reviewed realization.
- `platform/runtime-conformance.json` remains fixture data only; it must not
  become a second workload specification.
- Backstage remains optional as a portal and catalog UX layer over the stable
  center, not the source of truth.
- Provider-specific delivery and runtime tooling remain optional edge choices,
  not universal platform dependencies.

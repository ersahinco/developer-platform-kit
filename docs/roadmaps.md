# Roadmap

This document tracks platform maturity, near-term priorities, and deferred
decisions. Durable architecture belongs in canonical docs:

- [Architecture](architecture.md) owns repo shape and platform principles
- [Platform Contract](platform-contract.md) owns portable workload expectations
- [Platform Capabilities](platform-capabilities.md) owns the implemented
  capability surface
- [Deployment](deployment.md) and [Observability](observability.md) own current
  AWS operator behavior

## Current State

| Area | Current state | Why it matters |
|---|---|---|
| Repo model | Canonical split between `apps/`, `packages/`, `platform/`, `infra/`, and `scripts/` is now explicit. | Teams can place code without inventing new top-level patterns. |
| Workload metadata | `platform/workloads.json` is the workload intent source and `infra/app/workload_inventory.tf` is the AWS runtime realization layer. | This keeps workload identity and cloud fulfillment from drifting apart. |
| Delivery | Workflow ownership is split into app build, app deploy, infra plan, infra apply, security, and semgrep. | Cloud-changing actions stay reviewable and boring. |
| Runtime safety | Runtime conformance, contract tests, and architecture tests are part of the normal path. | Platform growth is constrained by executable guardrails, not memory. |
| Observability | Local OSS telemetry and AWS-native runtime signals are separated cleanly. | Operators get standard telemetry shapes without turning Terraform into a hosted observability stack. |
| Docs | Core docs now have clearer ownership and less overlap. | The repo is easier to onboard into and harder to misunderstand. |

## Near-Term Priorities

| Priority | Next move | Trigger |
|---|---|---|
| Runbook quality | Keep operator docs parameterized with Terraform outputs, stack placeholders, and runtime-owned commands. | Continue whenever a runbook still assumes the demo stack name or fixed region. |
| Workflow guardrails | Expand tests around workflow ownership boundaries and approved cloud-changing paths. | Add checks whenever a workflow picks up a new responsibility. |
| Workload onboarding | Keep the smallest supported workload patterns current in docs and tests. | Update only when a real workload introduces a genuinely new class or concern. |
| Observability inventory | Keep alarm, log-group, and evidence defaults derived from workload metadata where practical. | Tighten whenever a new workload or signal path adds handwritten inventory. |
| AWS runtime ergonomics | Prefer Terraform outputs, runtime inventory, and small scripts over repeated shell literals. | Refactor when examples or scripts duplicate stack-specific naming rules. |

## Maturity Direction

The target platform maturity is:

1. One clear workload contract.
2. One clear runtime realization layer per runtime.
3. Thin workload hosts and explicit adapters.
4. Split delivery ownership where review boundaries matter.
5. Operator docs that are runnable without tribal knowledge.
6. Standard tools used directly, with only small helper scripts at the edge.

The repo does not need a private framework to get there. The quality bar is
predictable extension, not maximal abstraction.

## Deferred Until Real Need

| Topic | Why it stays deferred |
|---|---|
| Second runtime target | Portability is already enforced at the boundary level; a demo runtime would add maintenance cost without operating value. |
| Broader Dapr scope | Pub/sub is the current real need. Actors, workflows, bindings, and secret APIs stay out until a workload truly needs them. |
| Analytics platform additions | dbt, orchestration, or warehouse tooling should arrive with an actual analytics requirement, not as platform theater. |
| Provider-neutral infra abstraction | The repo is stronger with direct Terraform and explicit AWS ownership than with speculative wrappers. |
| CloudWatch replacement | AWS-native alarms still back ECS rollback and managed-resource protection; replace only with a deliberate alternative, not by drift. |

## Decision Rules

- Standardize new platform behavior only after a real workload needs it.
- Prefer metadata plus tests over wrappers and generation.
- Keep contract growth portable and runtime implementation explicit.
- Add shared abstractions only after repeated pain is proven.
- Remove stale examples, duplicate docs, and dead workflow paths in the same
  slice that makes them obsolete.

## Recent Decisions

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-19 | Harden the repo around a single workload intent source and a separate AWS runtime realization layer. | This reduces drift without introducing a platform framework. |
| 2026-05-19 | Reframe runbooks and drills around outputs, placeholders, and operator-owned action. | Operational docs should survive stack renames and remain easy to run. |
| 2026-05-18 | Reframe the repo as a platform monorepo seed. | The repo now distinguishes workload hosts, shared packages, platform concerns, and runtime implementation clearly. |
| 2026-05-18 | Keep AWS-first portability by boundary as the default. | A standards-based, AWS-specific runtime is cleaner than speculative multi-runtime scaffolding. |
| 2026-05-13 | Retire the ECS-hosted LGTM and FireLens stack. | Learning value is in telemetry contracts and evidence, not a large observability control plane in Terraform. |
| 2026-04-30 | Use split manual workflows for cloud changes. | Reviewed plans and approved deploys are easier to reason about than one large cloud-changing pipeline. |

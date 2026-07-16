# Roadmap

Current priorities, decision rules, and deferred work. Durable architecture
lives in canonical docs:

- [Architecture](architecture.md)
- [Platform Contract](platform-contract.md)
- [Platform Capabilities](platform-capabilities.md)
- [Deployment](deployment.md)
- [Observability](observability.md)

## Current State

| Area | State |
|---|---|
| Repo model | canonical split across `apps/`, `packages/`, `platform/`, `infra/`, and `scripts/` |
| Stable center | workload contract plus platform catalog stay central; runtime targets realize them |
| Workload metadata | `platform/workloads.json` owns intent; `infra/app/workload_inventory.tf` fulfills it |
| Delivery | app build, app deploy, infra plan, infra apply, security, and semgrep stay split |
| Runtime safety | runtime conformance, contract tests, and architecture tests are normal gates |
| Pattern experiments | Dapr invocation plus booking consistency, late-event projection repair, and MLOps artifact lineage are local-only, contract-backed workloads |
| Observability | local OSS telemetry and AWS-native runtime signals stay separate |
| Docs | core docs are canonical, denser, and less duplicated |

## Near-Term Priorities

| Priority | Next move | Trigger |
|---|---|---|
| First-run clarity | keep `make help-*`, readiness views, and first-run docs aligned | a target is added, renamed, or promoted into the newcomer path |
| Runbook quality | keep operator docs parameterized with outputs, placeholders, and runtime-owned commands | any runbook still assumes a demo stack name or fixed region |
| Workflow guardrails | expand tests around workflow ownership and approved cloud-changing paths | a workflow picks up a new responsibility |
| Workload onboarding | keep workload classes and copy-from examples current in docs and tests | a workload or incubating capability introduces a new class or concern |
| Enterprise pattern depth | extend experiments through real failure modes and evidence, not product-name breadth | a consistency, event-time, ML, MLOps, or Dapr challenge needs a reproducible proof |
| Platform catalog shape | keep reusable modules, concerns, and templates recognizable as one catalog surface | catalog logic starts fragmenting across unrelated folders or scripts |
| Observability inventory | derive alarm, log-group, and evidence defaults from workload metadata where practical | a workload or signal path adds handwritten inventory |
| Runtime target ergonomics | prefer Terraform outputs, runtime inventory, and small scripts over repeated shell literals | examples or scripts duplicate target-specific naming rules |
| Hybrid reference hardening | exercise the Cloudflare, Hetzner, Supabase, S3, and Dapr composition through real operator evidence | live proof reveals a networking, recovery, or ownership gap |

## Lean Delivery Toolkit Next Slices

Track only outcome-level follow-up here. Remove rows when they no longer help
future agents keep the toolkit lean.

| Slice | Status | Outcome | Keep lean by |
|---|---|---|---|
| Command surface | baseline in place | newcomers can tell daily, proof, cloud, and operator commands apart from Make entrypoints | grouped Make help, not a new CLI |
| First-run proof | baseline in place | local diagnostics, local Compose proof, local Kubernetes proof, and AWS readiness are visibly separate | existing README and docs owners, not new process docs |
| Runtime guardrails | baseline in place | AWS-admitted workload realization fails loudly when the workload contract cannot be fulfilled | contract tests and narrow Terraform checks, not deployment DSL growth |
| Readiness evidence | baseline in place | workload maturity reports show local and AWS evidence without decoding platform history | report views, not orchestration |
| Provider composition | reference in place | explicit data, compute, and DNS roots prove a low-cost hybrid lane without a provider abstraction | stable catalog IDs and direct Terraform, not a composer DSL |

## Current Promotion Decision

Use `make workload-readiness` for the current local-first inventory and AWS
admission state. Do not admit a local-first workload to `aws-ecs` until a
concrete runtime owner accepts artifact storage, release workflow, operator
evidence, and incident response responsibilities. Local proof is enough to
exercise the delivery toolkit; cloud admission is a separate runtime-edge
decision.

## Maturity Direction

1. One workload contract.
2. One recognizable platform catalog.
3. One runtime realization layer per runtime.
4. Thin workload hosts and explicit adapters.
5. Split delivery ownership where review boundaries matter.
6. Operator docs runnable without tribal knowledge.
7. Standard tools used directly, with small helpers at the edge.

Rule: predictable extension over maximal abstraction.

## Deferred Until Real Need

| Topic | Why deferred |
|---|---|
| Runtime target activation | promote only with a concrete proof workload, owner, and realization plan |
| Broader Dapr scope | adopt building blocks through owned pattern proofs; pub/sub is production-proven and service invocation is local-proven |
| Analytics platform additions | should arrive with a real analytics requirement |
| Provider-neutral infra abstraction | direct Terraform plus explicit AWS ownership is cleaner |
| CloudWatch replacement | AWS-native alarms still back ECS rollback and managed-resource protection |

## Decision Rules

- incubate capabilities before broad demand only with an owner, concrete proof, contract, tests, evidence path, and honest maturity
- prefer metadata plus tests over wrappers and generation
- keep contract growth portable and runtime implementation explicit
- add shared abstractions only after repeated pain is proven
- remove stale examples, duplicate docs, and dead workflow paths in the same slice

## Recent Decisions

| Date | Decision |
|---|---|
| 2026-07-16 | Use standard Backstage entities and native GitHub workflow dispatch as the optional read-and-dispatch front door; keep GitHub Actions, Terraform, and release evidence authoritative, and keep Coolify/NetBird gated platform-edge candidates. |
| 2026-07-16 | Keep Dapr at the core application boundary; retain the consolidated component source, prove pub/sub and local service invocation, and grow other building blocks through owned experiments. |
| 2026-07-16 | Keep pattern-rich experimental workloads before broad adoption when they prove a concrete failure mode with ownership, contracts, tests, evidence, and honest maturity; remove hollow showcases and generic product laundry. |
| 2026-07-16 | Add a provider-composable starter reference with explicit Cloudflare DNS, Hetzner Compose, Supabase PostgreSQL, AWS S3, and Dapr boundaries; Terraform remains canonical and OpenTofu is compatibility-only. |
| 2026-06-14 | Keep lean delivery toolkit follow-up as small slices: command clarity, first-run proof, runtime guardrails, and readiness evidence; do not add portals, generators, provider abstractions, Helm/CRD surfaces, or new runtime targets. |
| 2026-05-21 | Treat the workload contract and platform catalog as the stable center; runtime targets are pluggable realizations. |
| 2026-05-19 | Harden one workload intent source and one AWS runtime realization layer. |
| 2026-05-19 | Reframe runbooks and drills around outputs, placeholders, and operator-owned action. |
| 2026-05-18 | Reframe the repo as a platform monorepo seed. |
| 2026-05-18 | Keep portability by boundary as the default while AWS remains the primary runtime target. |
| 2026-05-13 | Retire the ECS-hosted LGTM and FireLens stack. |
| 2026-04-30 | Use split manual workflows for cloud changes. |

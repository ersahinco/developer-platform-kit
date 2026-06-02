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
| Observability | local OSS telemetry and AWS-native runtime signals stay separate |
| Docs | core docs are canonical, denser, and less duplicated |

## Near-Term Priorities

| Priority | Next move | Trigger |
|---|---|---|
| Runbook quality | keep operator docs parameterized with outputs, placeholders, and runtime-owned commands | any runbook still assumes a demo stack name or fixed region |
| Workflow guardrails | expand tests around workflow ownership and approved cloud-changing paths | a workflow picks up a new responsibility |
| Workload onboarding | keep workload classes and copy-from examples current in docs and tests | a real workload introduces a new class or concern |
| Platform catalog shape | keep reusable modules, concerns, and templates recognizable as one catalog surface | catalog logic starts fragmenting across unrelated folders or scripts |
| Observability inventory | derive alarm, log-group, and evidence defaults from workload metadata where practical | a workload or signal path adds handwritten inventory |
| Runtime target ergonomics | prefer Terraform outputs, runtime inventory, and small scripts over repeated shell literals | examples or scripts duplicate target-specific naming rules |
| Provider horizon clarity | keep managed DB and DNS provider edges documented as future cost or hybrid options, not implied implementations | docs or metadata start blurring horizon intent with reviewed runtime capability |

## Current Promotion Decision

The data, churn, and support-triage LLM workloads are local-first only:

- `lake_orders_ingest_job`
- `churn_model_train_job`
- `churn_prediction_api`
- `support_triage_llm`

Do not admit these workloads to `aws-ecs` until a concrete runtime owner accepts
artifact storage, release workflow, operator evidence, and incident response
responsibilities. Local proof is complete enough to exercise the delivery
toolkit; cloud admission is a separate runtime-edge decision.

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
| Runtime target expansion | add only with a concrete workload need, owner, and realization plan |
| Broader Dapr scope | pub/sub is the only current need |
| Analytics platform additions | should arrive with a real analytics requirement |
| Provider-neutral infra abstraction | direct Terraform plus explicit AWS ownership is cleaner |
| CloudWatch replacement | AWS-native alarms still back ECS rollback and managed-resource protection |

## Decision Rules

- standardize new platform behavior only after a real workload needs it
- prefer metadata plus tests over wrappers and generation
- keep contract growth portable and runtime implementation explicit
- add shared abstractions only after repeated pain is proven
- remove stale examples, duplicate docs, and dead workflow paths in the same slice

## Recent Decisions

| Date | Decision |
|---|---|
| 2026-06-02 | Keep the new data, churn, and support-triage LLM workloads local-first until runtime ownership and cloud evidence paths are reviewed. |
| 2026-05-21 | Treat the workload contract and platform catalog as the stable center; runtime targets are pluggable realizations. |
| 2026-05-19 | Harden one workload intent source and one AWS runtime realization layer. |
| 2026-05-19 | Reframe runbooks and drills around outputs, placeholders, and operator-owned action. |
| 2026-05-18 | Reframe the repo as a platform monorepo seed. |
| 2026-05-18 | Keep portability by boundary as the default while AWS remains the primary runtime target. |
| 2026-05-13 | Retire the ECS-hosted LGTM and FireLens stack. |
| 2026-04-30 | Use split manual workflows for cloud changes. |

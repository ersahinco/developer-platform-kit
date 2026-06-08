# Documentation

Canonical doc map. Find the owner before adding a new page.

## Canonical Owners

| Topic | Owning doc | Use it for |
|---|---|---|
| First local-to-cloud validation pass | [First 30 Minutes](first-30-minutes.md) | New developer happy path through local proof and safe cloud readiness |
| Repo shape and ownership boundaries | [Architecture](architecture.md) | Where code, Terraform, scripts, and docs belong |
| Portable workload expectations | [Platform Contract](platform-contract.md) | Workload contract, metadata ownership, external contract rules |
| Current platform capability surface | [Platform Capabilities](platform-capabilities.md) | What exists today and where to extend it |
| Runtime-target evaluation | [Runtime Toolkit](runtime-toolkit.md) | When and how to add another runtime target |
| Runtime defaults | [Runtime Defaults](runtime-defaults.md) | Blessed auth, identity, secrets, observability, policy, CI/CD, and network defaults |
| Local workflow | [Local Development](local-development.md) | Setup, migrations, local services |
| AWS delivery and operator flow | [Deployment](deployment.md) | Workflow ownership, rollout sequence, review loop |
| Operator day-2 commands | [Operator Day 2 Commands](operator-day-2.md) | Exact commands for readiness, deploy observation, evidence, and integration checks |
| Operational telemetry | [Observability](observability.md) | Local and cloud telemetry wiring and checks |
| Workload observability | [Workload Observability](workload-observability.md) | Required service metrics, structured logs, job events, and operator payload shape |
| Current work state | [Roadmaps](roadmaps.md) | Continuation notes, deferred work, project status |

## Fast Paths

| Task | Read |
|---|---|
| Validate the toolkit quickly | [First 30 Minutes](first-30-minutes.md) |
| Review a platform-facing change | [Architecture](architecture.md), [Platform Contract](platform-contract.md), [Operator Day 2 Commands](operator-day-2.md) |
| Learn the vocabulary | [Ubiquitous Language](ubiquitous-language.md) |
| Understand the monorepo model | [Architecture](architecture.md), [ADR 0001](adr/0001-aws-first-platform-monorepo-seed.md), [ADR 0002](adr/0002-stable-center-and-pluggable-runtime-targets.md) |
| Understand the platform itself | [Platform Contract](platform-contract.md), [Platform Capabilities](platform-capabilities.md) |
| Add a workload | [Adding Workloads](adding-workloads.md), `make workload-readiness`, `make workload-readiness-check`, [Platform Contract](platform-contract.md#workload-checklist) |
| Work locally | [Local Development](local-development.md), `make platform-doctor` |
| Deploy or operate AWS | [Operator Day 2 Commands](operator-day-2.md), [Deployment](deployment.md), [Infrastructure](../infra/README.md), [Runbooks](runbooks/README.md) |
| Add or evaluate another runtime | [Runtime Toolkit](runtime-toolkit.md), [Runtime Defaults](runtime-defaults.md), `make enterprise-runtime-fit-check` |
| Work on telemetry or release evidence | [Workload Observability](workload-observability.md), [Observability](observability.md) |

## Critical Review

For platform-facing changes, use a short multi-lens review before adding new
machinery:

1. Architecture: does the change preserve the workload contract, platform
   catalog, and runtime-target boundary?
2. Data and evidence: can release evidence, operator payloads, and incident
   evidence still be correlated by workload, run id, image tag, and timestamp?
3. Security: are trust boundaries, secrets, and release controls explicit?
4. Operations: does the change fit the path in
   [Operator Day 2 Commands](operator-day-2.md)?
5. Pragmatism: can a smaller doc, test, or command clarification solve the same
   problem without adding a new layer?

## Rules

- `README.md` is the short project entrypoint.
- `docs/README.md` is the doc map.
- `docs/deployment.md` owns shared deploy, apply, and evidence review commands.
- `docs/runbooks/` owns operator action, not platform design.
- Do not add a new doc when an owner above already covers the topic.

# Documentation

This is the canonical documentation map. Use it to find the owning doc for a
topic before adding a new page.

## Canonical Docs

| Topic | Owning doc | Use it for |
|---|---|---|
| Repo shape and ownership boundaries | [Architecture](architecture.md) | Where code, Terraform, scripts, and docs belong |
| Portable workload expectations | [Platform Contract](platform-contract.md) | What workloads must expose and what `platform/workloads.json` owns |
| Current standardized capability surface | [Platform Capabilities](platform-capabilities.md) | What the platform currently provides and where to extend it |
| Runtime-target evaluation | [Runtime Toolkit](runtime-toolkit.md) | When and how to add another hosting runtime |
| Local workflow | [Local Development](local-development.md) | Day-to-day setup and migration walkthrough |
| AWS delivery and rollout | [Deployment](deployment.md) | Bootstrap, pipeline shape, and rollout sequence |
| Operational telemetry | [Observability](observability.md) | Local/cloud observability wiring and validation |
| Current work state | [Roadmaps](roadmaps.md) | Continuation notes, deferred work, and project status |

## Reading Paths

| Task | Read |
|---|---|
| Learn the vocabulary | [Ubiquitous Language](ubiquitous-language.md) |
| Understand the monorepo model | [Architecture](architecture.md), [ADR 0001](adr/0001-aws-first-platform-monorepo-seed.md) |
| Understand the platform itself | [Platform Contract](platform-contract.md), [Platform Capabilities](platform-capabilities.md) |
| Add a workload | [Adding Workloads](adding-workloads.md), [Platform Contract](platform-contract.md#workload-checklist) |
| Work locally | [Local Development](local-development.md) |
| Deploy or operate AWS | [Deployment](deployment.md), [Infrastructure](../infra/README.md), [Runbooks](runbooks/README.md) |
| Add or evaluate another runtime | [Runtime Toolkit](runtime-toolkit.md) |
| Work on telemetry or release evidence | [Observability](observability.md), [Platform Contract](platform-contract.md#observability) |

## Ownership Rules

- `README.md` is the short project entrypoint.
- `docs/README.md` is the canonical map; prefer linking to it from summary docs.
- `docs/architecture.md` owns repo boundaries and placement rules.
- `docs/platform-contract.md` owns portable workload expectations.
- `docs/platform-capabilities.md` owns the current capability inventory, not the
  abstract contract.
- `docs/runtime-toolkit.md` owns multi-runtime evaluation rules, not current
  AWS rollout details.
- `docs/roadmaps.md` owns current state, continuation notes, and deferred work.
- Runbooks and drills describe operator action, not platform design.
- Do not add a new doc when one of the canonical docs above already owns the
  topic.

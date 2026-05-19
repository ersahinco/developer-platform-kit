# Documentation

This is the canonical map for project docs. Keep this file grouped by task so
the README, roadmap, and architecture docs can stay short.

## Start Here

| Task | Read |
|---|---|
| Learn the shared vocabulary | [Ubiquitous Language](ubiquitous-language.md) |
| Understand the project shape | [Architecture](architecture.md), [Roadmap](roadmaps.md) |
| Understand the platform monorepo decision | [ADR 0001](adr/0001-aws-first-platform-monorepo-seed.md) |
| Continue work cleanly | [Roadmap](roadmaps.md) |
| Develop locally | [Local Development](local-development.md) |
| Deploy or operate AWS | [Deployment](deployment.md), [Infrastructure](../infra/README.md), [Runbooks](runbooks/README.md), [App Dependency Readiness Drill](drills/app-dependency-readiness.md) |

## Platform Toolkit Contracts

| Task | Read |
|---|---|
| Understand the portable workload contract | [Platform Contract](platform-contract.md) |
| Add a workload | [Adding Workloads](adding-workloads.md), [Platform Contract](platform-contract.md#workload-checklist) |
| See the current platform capability surface | [Platform Capabilities](platform-capabilities.md) |
| Understand the temporary application specification | [Platform Contract](platform-contract.md#application-specification) |
| Add or evaluate a runtime target | [Runtime Toolkit](runtime-toolkit.md) |
| Keep provider edges portable | [Data](data.md), [Platform Contract](platform-contract.md#eventing) |

## Delivery And Operations

| Task | Read |
|---|---|
| Understand CI and quality gates | [DevOps Toolchain](devops-toolchain.md) |
| Understand data movement | [Data](data.md) |
| Add or operate telemetry | [Observability](observability.md), [Platform Contract](platform-contract.md#observability) |
| Handle incidents | [Runbooks](runbooks/README.md) |
| Practice failure paths | [App Dependency Readiness Drill](drills/app-dependency-readiness.md) |

## Ownership Rules

- `README.md` is the short public project entrypoint.
- `docs/README.md` is the canonical documentation map.
- `docs/roadmaps.md` tracks state, current work, decisions, and deferred work.
- Use `docs/roadmaps.md` for continuation rules and current working style.
- `docs/architecture.md` owns both design rationale and repo/control-boundary
  ownership.
- Canonical docs define reusable platform expectations; runbooks and drills
  describe concrete operator actions.
- Do not add a new doc when an existing canonical doc owns the topic.

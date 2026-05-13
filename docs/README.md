# Documentation

This is the canonical map for project docs. Keep this file grouped by job so
the README, roadmap, and architecture docs can stay short.

## Start Here

| Job | Read |
|---|---|
| Learn the shared vocabulary | [Ubiquitous Language](ubiquitous-language.md) |
| Understand the project shape | [Architecture](architecture.md), [Architecture Layout](architecture-layout.md), [Roadmap](roadmaps.md) |
| Continue work cleanly | [Engineering Loop](engineering-loop.md), [Roadmap](roadmaps.md) |
| Develop locally | [Local Development](local-development.md) |
| Deploy or operate AWS | [Deployment](deployment.md), [Infrastructure](../infra/README.md), [Runbooks](runbooks/README.md), [Drills](drills/README.md) |

## Platform Toolkit Contracts

| Job | Read |
|---|---|
| Understand the portable workload contract | [Platform Contract](platform-contract.md) |
| Add a workload | [Workload Toolkit](workload-toolkit.md) |
| Add or evaluate a runtime target | [Runtime Toolkit](runtime-toolkit.md), [Portability Status](portability-status.md) |
| Keep provider edges portable | [Data](data.md), [Dapr Portability Contract](dapr-portability-contract.md), [Config And Secrets Contract](config-secrets-contract.md) |

## Delivery And Operations

| Job | Read |
|---|---|
| Understand CI and quality gates | [DevOps Toolchain](devops-toolchain.md), [CI Quality Contract](ci-quality-contract.md) |
| Understand data movement | [Data](data.md) |
| Add or operate telemetry | [Observability](observability.md), [Observability Onboarding Contract](observability-onboarding-contract.md), [Operator Observability Map](operator-observability-map.md) |
| Handle incidents | [Runbooks](runbooks/README.md) |
| Practice failure paths | [Drills](drills/README.md) |

## Ownership Rules

- `README.md` is the short public project entrypoint.
- `docs/README.md` is the canonical documentation map.
- `docs/roadmaps.md` tracks state, current work, decisions, and deferred work.
- `docs/architecture.md` keeps design rationale; `docs/architecture-layout.md`
  keeps repo/control-boundary ownership.
- Contract docs define reusable platform expectations; runbooks and drills
  describe concrete operator actions.
- Do not add a new doc when an existing canonical doc owns the topic.

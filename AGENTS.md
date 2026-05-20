# aws-sdlc-containers - Agent Rules

Cross-tool base rules for Codex, OpenCode, and other agents in this repo.
Kiro reads `.kiro/steering/` for the richer scoped layer.

Short form: standardize the delivery workflow, do not replace the tools.

## Canonicality

- `AGENTS.md` is the canonical shared agent-memory surface.
- `CLAUDE.md` is a shim that imports this file for Claude Code / Kiro.
- `opencode.json` only points OpenCode at this file.
- `.kiro/steering/` exists only for Kiro file-scoped rules and Kiro skill files.

## Vocabulary

| Use | Avoid |
|---|---|
| delivery toolkit | framework, custom framework |
| workload | microservice |
| portable by boundary | cloud-neutral |
| platform edge | cloud abstraction layer |
| runtime target | cloud provider |
| app host | service, microservice |

## Layer Map

| Path | Owns | Must not own |
|---|---|---|
| `packages/domain/` | Entities, value objects, domain events | Provider SDKs, framework imports, runtime details |
| `packages/application/` | Use cases, ports, workflow logic | SQL, Dapr internals, AWS SDK |
| `packages/infrastructure/` | SQLAlchemy, Dapr, S3, runtime adapters | Domain/application policy |
| `apps/*/` | Workload host: settings, routes, lifecycle, wiring | Business logic that belongs in `packages/` |
| `platform/workloads.json` | Workload identity, operational class, ports, config/secret names | Deployment choreography |
| `platform/concerns/` | Shared runtime capabilities: Dapr, observability, security | App-specific business rules |
| `infra/platform/` | Bootstrap, network, GitHub OIDC | Workload identity |
| `infra/app/` | RDS, ECS, ALB, jobs, messaging | Domain/application logic |
| `infra/catalog/` | Reusable AWS building blocks | Deploy-root orchestration |
| `db/` | Liquibase changelog, bootstrap SQL, PgBouncer assets | App logic |
| `scripts/` | CI, release, operator, observability, data helpers | Hidden framework layers |
| `tests/` | API, application, runtime, infrastructure, contract checks | Production code |
| `.github/workflows/` | CI gates, app build/deploy, infra plan/apply, security | App or Terraform business logic |

Dependency direction is inward only:

```text
apps/* -> packages/application -> packages/domain
apps/* -> packages/infrastructure
packages/infrastructure -> packages/application + packages/domain
```

Provider resource names belong at the platform edge, never in domain or
application code.

## Workload Classes

Declare one class in `platform/workloads.json` for every workload:

| Class | Description |
|---|---|
| `edge-service` | User-facing or externally routed HTTP service |
| `internal-service` | Long-running service without public edge ownership |
| `operator-job` | One-off task triggered manually or by CI/operator |
| `scheduled-job` | Recurring task triggered by a scheduler |

Current: `api` -> `edge-service`; `order_event_consumer` -> `internal-service`;
`backfill_worker` -> `operator-job`; `data_export_job` -> `scheduled-job`

## Workload Contract

Services must provide:

- OCI image declared in `platform/workloads.json`
- `/health`, `/ready`, `/metrics`
- Prometheus metrics
- Structured logs with stable workload identifiers
- Environment-variable or mounted-file configuration
- Runtime secret injection; never bake secrets into images

Jobs must provide:

- Meaningful process exit status
- Safe rerun behavior or clearly bounded idempotency
- Structured start, progress, success, and failure events
- The same config and secret rules as services

## Metadata Ownership

1. `platform/workloads.json` - what the workload is
2. `platform/runtime-conformance.json` - local/CI fixture data only
3. `infra/app/workload_inventory.tf` - how AWS fulfills the contract

Rules:

- Do not grow `platform/workloads.json` into a deployment DSL.
- Do not let `infra/app/workload_inventory.tf` redefine workload identity.
- Do not let `platform/runtime-conformance.json` grow second application-spec semantics.

## Eventing Boundary

Dapr is the app-facing eventing boundary. Application code may know Dapr
pub/sub names, topics, CloudEvents, and outbox semantics. Application code
must not know whether the runtime uses SNS/SQS, Redis, Kafka, or another
broker. The durable handoff is the database outbox.

## Delivery Rules

- Build before deploy.
- Plan before apply.
- Use immutable image tags; never `latest`.
- Emit release evidence for every cloud-changing workflow.
- Keep build and deploy separate.
- Keep plan and apply separate.

## Agentic Development

- Favor more with less.
- Prefer simplification over feature expansion when both solve the same problem.
- Remove duplication, hidden coupling, and unclear ownership first.
- Keep the repo conventional: standard tools directly, small helpers only.
- Do not add speculative abstractions, internal frameworks, or extra layers.
- Preserve explicit platform boundaries, metadata ownership, and reviewed delivery.

## Checklists

Adding a workload:

1. Add `apps/<name>/main.py`, `config.py`, `pyproject.toml`.
2. Register it in `platform/workloads.json` before Terraform resources.
3. Reuse `platform/workload.Dockerfile` unless there is a documented reason not to.
4. Services expose `/health`, `/ready`, `/metrics`.
5. Jobs emit structured events and document idempotency.
6. Add pytest coverage and keep `make runtime-conformance` passing.

Schema changes:

1. Expand - add nullable columns or tables; old code still works.
2. Dual-write - new code writes both shapes.
3. Backfill - migrate existing data via `apps/backfill_worker/`.
4. Switch - new code reads new shape only.
5. Contract - remove old columns or tables.

Quality gates:

```bash
make lint
make secret-scan
make dependency-audit
uv run pytest tests/ -v
make runtime-conformance
```

Terraform: `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed
plan, separate apply.

## Intentionally Not Here

Do not add without a real workload need:

- Dapr state store, bindings, workflows, actors, or secrets
- Kubernetes, Helm, Kustomize, or Crossplane
- A second cloud/runtime target
- Generic provider-neutral infrastructure modules

## Scoped Rules

Codex loads these automatically in the relevant subtree:

| Path | Nested AGENTS.md |
|---|---|
| `packages/` | `packages/AGENTS.md` |
| `apps/` | `apps/AGENTS.md` |
| `infra/` | `infra/AGENTS.md` |
| `tests/` | `tests/AGENTS.md` |
| `db/` | `db/AGENTS.md` |
| `.github/workflows/` | `.github/AGENTS.md` |

## On-Demand Skills

| Skill file | Load when |
|---|---|
| `.kiro/steering/skill-clean-architecture.md` | Refactoring across packages/apps boundary |
| `.kiro/steering/skill-ddd.md` | Domain modeling, aggregates, domain events |
| `.kiro/steering/skill-release-it.md` | Services, health checks, Dapr, production reliability |
| `.kiro/steering/skill-ddia.md` | Schema changes, outbox, backfill, idempotency |
| `.kiro/steering/skill-pragmatic-programmer.md` | General engineering, automation, tech debt |
| `.kiro/steering/skill-refactoring.md` | Refactoring passes, module boundary cleanup |

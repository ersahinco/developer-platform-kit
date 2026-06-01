# aws-sdlc-containers - Agent Rules

Canonical shared agent-memory surface for Codex, OpenCode, Claude Code, Kiro,
and other agents in this repo.

Short form: standardize the delivery workflow, do not replace the tools.

## Canonicality

- `AGENTS.md` is the canonical shared agent-memory surface.
- `CLAUDE.md` is a shim that imports this file for Claude Code / Kiro.
- `opencode.json` only points OpenCode at this file.
- Nested `AGENTS.md` files provide scoped rules by subtree.
- `.kiro/steering/` is kept only for manual skill files.

## Vocabulary

| Use | Avoid |
|---|---|
| delivery toolkit | framework, custom framework |
| workload | microservice |
| platform catalog | internal framework, magic scaffolding |
| portable by boundary | cloud-neutral |
| platform edge | cloud abstraction layer |
| runtime target | cloud provider |
| app host | service, microservice |

## Stable Center

The stable center of the platform is the workload contract and the platform
catalog.

- The workload contract defines what a workload is, what it needs, and what guarantees it must satisfy.
- The platform catalog provides reusable building blocks, templates, modules, policies, and delivery paths that realize those needs.
- A runtime target is a pluggable implementation choice at the platform edge, such as local Compose, AWS ECS, jobs, or a future provider-edge integration backed by a real workload need.
- Runtime targets must realize the contract, not redefine workload identity, portability rules, or shared delivery policy.
- The current local runtime target is Docker Compose. The current reviewed production runtime target is AWS/ECS. Additional runtime targets need a real workload reason and clear ownership.

## Layer Map

| Path | Owns | Must not own |
|---|---|---|
| `packages/domain/` | Entities, value objects, domain events | Provider SDKs, framework imports, runtime details |
| `packages/application/` | Use cases, ports, workflow logic | SQL, Dapr internals, AWS SDK |
| `packages/infrastructure/` | SQLAlchemy, Dapr, S3, runtime adapters | Domain/application policy |
| `apps/*/` | Workload host: settings, routes, lifecycle, wiring | Business logic that belongs in `packages/` |
| `platform/workloads.json` | Workload identity, operational class, use-case tags, ports, config/secret names | Deployment choreography or runtime-specific wiring |
| `platform/concerns/` | Shared runtime capabilities: Dapr, observability, security | App-specific business rules |
| `infra/platform/` | Bootstrap, network, GitHub OIDC | Workload identity |
| `infra/app/` | RDS, ECS, ALB, jobs, messaging | Domain/application logic |
| `infra/catalog/` | Reusable catalog building blocks for runtime targets; current AWS catalog lives here | Deploy-root orchestration or workload identity |
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

Current: `api` -> `edge-service`; `event_consumer` -> `internal-service`;
`backfill_worker` -> `operator-job`; `data_export_job` -> `scheduled-job`;
`operational_snapshot_job` -> `operator-job`; `integration_check_job` -> `operator-job`

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
3. `infra/app/workload_inventory.tf` - how the current AWS runtime fulfills the contract

Rules:

- Do not grow `platform/workloads.json` into a deployment DSL.
- Do not let runtime realization layers such as `infra/app/workload_inventory.tf` redefine workload identity.
- Do not let `platform/runtime-conformance.json` grow second application-spec semantics.
- Use target-neutral `use_cases` to classify workload intent for catalog, templates, and self-service discovery.
- Add future runtime targets as parallel realization layers, not by rewriting the stable center.

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
- open-source data load / DuckDB / dbt example stacks in the deployable workload contract
- Self-managed Kubernetes control planes, Helm/Kustomize packaging, or Crossplane
- A runtime target added only to prove portability
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

## Manual Skills

| Skill file | Load when |
|---|---|
| `.kiro/steering/skill-clean-architecture.md` | Refactoring across packages/apps boundary |
| `.kiro/steering/skill-ddd.md` | Domain modeling, aggregates, domain events |
| `.kiro/steering/skill-release-it.md` | Services, health checks, Dapr, production reliability |
| `.kiro/steering/skill-ddia.md` | Schema changes, outbox, backfill, idempotency |
| `.kiro/steering/skill-pragmatic-programmer.md` | General engineering, automation, tech debt |
| `.kiro/steering/skill-refactoring.md` | Refactoring passes, module boundary cleanup |

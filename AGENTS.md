# aws-sdlc-containers — Agent Rules

This is the cross-tool base rule set for Codex, OpenCode, and any other agent
working in this repository. Kiro reads `.kiro/steering/` for the full scoped
layer on top of this file.

Short form: **standardize the delivery workflow, do not replace the tools.**

---

## Vocabulary — Use These Terms

| Use | Avoid |
|---|---|
| delivery toolkit | framework, custom framework |
| workload | microservice |
| portable by boundary | cloud-neutral |
| platform edge | cloud abstraction layer |
| runtime target | cloud provider |
| app host | service, microservice |

---

## Repository Layer Map

```
packages/domain/          pure entities, value objects, domain events
                          NO provider SDKs, NO framework imports, NO runtime details

packages/application/     use cases, ports (interfaces), workflow logic
                          NO SQL, NO Dapr internals, NO AWS SDK

packages/infrastructure/  SQLAlchemy, Dapr, S3, and all runtime adapters
                          implements ports from packages/application/

apps/*/                   workload host: settings, routes, lifecycle, wiring
                          keep thin — business logic lives in packages/

platform/workloads.json   workload identity, operational class, ports, config/secret names
platform/concerns/        shared runtime capabilities: Dapr, observability, security
infra/platform/           bootstrap, network, GitHub OIDC
infra/app/                runtime resources: RDS, ECS, ALB, jobs, messaging
infra/catalog/            reusable AWS building blocks (library, not a deploy root)
db/                       Liquibase changelog, bootstrap SQL, PgBouncer assets
scripts/                  CI, release, operator, observability, data helpers
tests/                    API, application, runtime, infrastructure, contract checks
.github/workflows/        CI gates, app build/deploy, infra plan/apply, security
```

**Dependency direction is inward — never reverse it:**

```
apps/*  →  packages/application  →  packages/domain
apps/*  →  packages/infrastructure
packages/infrastructure  →  packages/application + packages/domain
```

Provider resource names (bucket names, queue ARNs, task definitions, IAM roles)
belong at the platform edge — never in domain or application code.

---

## Workload Operational Classes

Declare one of these in `platform/workloads.json` for every workload:

| Class | Description |
|---|---|
| `edge-service` | User-facing or externally routed HTTP service |
| `internal-service` | Long-running service without public edge ownership |
| `operator-job` | One-off task triggered manually or by CI/operator |
| `scheduled-job` | Recurring task triggered by a scheduler |

Current: `api` → edge-service · `order_event_consumer` → internal-service ·
`backfill_worker` → operator-job · `data_export_job` → scheduled-job

---

## Workload Contract — Non-Negotiable

**Service workloads** must provide:
- OCI image declared in `platform/workloads.json`
- `/health`, `/ready`, `/metrics` endpoints
- Prometheus metrics
- Structured logs with stable workload identifiers
- Environment-variable or mounted-file configuration
- Runtime secret injection — never bake secrets into images

**Job workloads** must provide:
- Meaningful process exit status
- Safe rerun behavior or clearly bounded idempotency
- Structured start / progress / success / failure events
- Same config and secret rules as services

---

## Metadata Ownership — Three Layers Only

1. `platform/workloads.json` — what the workload **is**
2. `platform/runtime-conformance.json` — local/CI fixture data only
3. `infra/app/workload_inventory.tf` — how AWS **fulfills** the contract

Do not grow `platform/workloads.json` into a deployment DSL.
Do not let `infra/app/workload_inventory.tf` redefine workload identity.

---

## Eventing Boundary

Dapr is the app-facing eventing boundary. Application code may know Dapr
pub/sub names, topics, CloudEvents, and outbox semantics. Application code
must not know whether the runtime uses SNS/SQS, Redis, Kafka, or another
broker. The durable handoff is the database outbox.

---

## Delivery Shape — Review-First

- Build before deploy · Plan before apply
- Immutable image tags (Git SHA) — never `latest`
- Emit release evidence for every cloud-changing workflow
- Build and deploy are separate workflows — do not merge them
- Plan and apply are separate workflows — do not merge them

---

## Adding a New Workload

1. Add `apps/<name>/main.py`, `config.py`, `pyproject.toml`
2. Register in `platform/workloads.json` **before** any Terraform resources
3. Reuse `platform/workload.Dockerfile` unless there is a documented reason not to
4. Services: expose `/health`, `/ready`, `/metrics`
5. Jobs: emit structured events, document idempotency
6. Add pytest coverage · keep `make runtime-conformance` passing

---

## Schema Changes — Expand/Contract Always

Never make a breaking schema change in a single migration:
1. Expand — add nullable columns/tables; old code still works
2. Dual-write — new code writes both shapes
3. Backfill — migrate existing data via `apps/backfill_worker/`
4. Switch — new code reads new shape only
5. Contract — remove old columns/tables

---

## Quality Gates — Run Before Calling a Change Done

```bash
make lint                 # Ruff, Pyright, actionlint, hadolint, lychee
make secret-scan          # Gitleaks
make dependency-audit     # pip-audit
uv run pytest tests/ -v   # full test suite
make runtime-conformance  # external contract proof
```

Terraform: `terraform fmt` · `terraform validate` · TFLint · Checkov ·
reviewed plan · separate apply.

---

## What Is Intentionally Not Here

Do not add without a real workload need:
- Dapr state store, bindings, workflows, actors, or secrets
- Kubernetes, Helm, Kustomize, or Crossplane
- A second cloud/runtime target
- Generic provider-neutral infrastructure modules

---

## Scoped Rules (Codex: nested AGENTS.md)

Codex loads these automatically when working in the relevant subtree:

| Path | Nested AGENTS.md |
|---|---|
| `packages/` | `packages/AGENTS.md` |
| `apps/` | `apps/AGENTS.md` |
| `infra/` | `infra/AGENTS.md` |
| `tests/` | `tests/AGENTS.md` |
| `db/` | `db/AGENTS.md` |
| `.github/workflows/` | `.github/AGENTS.md` |

## On-Demand Skills

Load these for specific work types (reference in chat or as a Codex skill):

| Skill file | Load when |
|---|---|
| `.kiro/steering/skill-clean-architecture.md` | Refactoring across packages/apps boundary |
| `.kiro/steering/skill-ddd.md` | Domain modeling, aggregates, domain events |
| `.kiro/steering/skill-release-it.md` | Services, health checks, Dapr, production reliability |
| `.kiro/steering/skill-ddia.md` | Schema changes, outbox, backfill, idempotency |
| `.kiro/steering/skill-pragmatic-programmer.md` | General engineering, automation, tech debt |
| `.kiro/steering/skill-refactoring.md` | Refactoring passes, module boundary cleanup |

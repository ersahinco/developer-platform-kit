---
inclusion: always
---

# Platform Monorepo — Agent Base Rules

This is the always-on rule set for the `aws-sdlc-containers` platform monorepo.
Every agent session in this repo must follow these rules regardless of the task.

## Project Identity

This repo is an **opinionated cloud-native delivery toolkit** — not a private framework.
Short form: standardize the delivery workflow, do not replace the tools.

Say "delivery toolkit", not "framework".
Say "workload", not "microservice".
Say "portable by boundary", not "cloud-neutral".
Say "platform edge", not "cloud abstraction layer".
Say "runtime target", not "cloud provider".

---

## Layer Ownership — Where Code Belongs

| Path | Owns |
|---|---|
| `packages/domain/` | Pure entities, value objects, domain events. No provider SDKs, no framework imports, no runtime details. |
| `packages/application/` | Use cases, ports, workflow logic. No SQL, no Dapr internals, no AWS SDK. |
| `packages/infrastructure/` | SQLAlchemy, Dapr, S3, and all runtime adapters. Implements ports from `packages/application/`. |
| `apps/*/` | Workload host: settings, HTTP routes, process lifecycle, dependency assembly. Keep thin. |
| `platform/workloads.json` | Workload identity, operational class, ports, Dapr intent, config/secret names, portable expectations. |
| `platform/concerns/` | Shared runtime capabilities: Dapr, observability, security, policy, networking. |
| `infra/catalog/` | Reusable AWS building blocks. |
| `infra/platform/` | Bootstrap, network, GitHub OIDC. |
| `infra/app/` | Runtime resources: RDS, ECS, ALB, jobs, messaging, observability wiring. |
| `scripts/` | CI, release, operator, observability, data helpers. Explicit edge automation only. |
| `tests/` | API, application, runtime, infrastructure, and contract checks. |
| `.github/workflows/` | CI gates, app build/deploy, infra plan/apply, security. |
| `db/` | Liquibase changelog, bootstrap SQL, PgBouncer assets. |

**Dependency direction is inward and must never be reversed:**

```
apps/*  →  packages/application  →  packages/domain
apps/*  →  packages/infrastructure
packages/infrastructure  →  packages/application + packages/domain
```

Provider resource names (buckets, queues, task definitions, IAM roles) belong at the platform edge — never in domain or application code.

---

## Workload Operational Classes

Every workload must declare one of these classes in `platform/workloads.json`:

| Class | Description |
|---|---|
| `edge-service` | User-facing or externally routed HTTP service |
| `internal-service` | Long-running service without public edge ownership |
| `operator-job` | One-off task triggered manually or by CI/operator workflow |
| `scheduled-job` | Recurring task triggered by a scheduler |

Current mapping: `api` → `edge-service`, `order_event_consumer` → `internal-service`, `backfill_worker` → `operator-job`, `data_export_job` → `scheduled-job`.

---

## Workload Contract — Non-Negotiable Requirements

Every **service workload** must provide:
- A committed OCI image declared in `platform/workloads.json`
- A stable reference host under `apps/`
- A declared HTTP service port
- `/health`, `/ready`, and `/metrics` endpoints
- Prometheus metrics
- Structured logs with stable runtime labels and workload identifiers
- Environment-variable or mounted-file configuration
- Runtime secret injection — never bake secret values into images
- Optional OTLP/HTTP traces when they materially help debugging

Every **job workload** must provide:
- A committed OCI image
- Meaningful process exit status
- Safe rerun behavior or clearly bounded idempotency
- Structured start, progress, success, and failure events
- The same config and secret rules as services

---

## Metadata Ownership — Three Layers Only

1. `platform/workloads.json` — what the workload **is**: identity, operational class, app path, shared image metadata, declared config names, service port shape, Dapr intent, portable expectations
2. `platform/runtime-conformance.json` — local/CI fixture data only for `make runtime-conformance`
3. `infra/app/workload_inventory.tf` — how the current AWS runtime **fulfills** the contract

Do not grow `platform/workloads.json` into a deployment DSL.
Do not let `infra/app/workload_inventory.tf` redefine workload identity.
Do not let `platform/runtime-conformance.json` grow second application-spec semantics.

---

## Configuration and Secrets

- Declare workload config and secrets in `platform/workloads.json`
- Prefer names that describe application intent, not provider plumbing
- Keep secret values out of committed files, Docker layers, tfvars, and logs
- Keep `Settings` classes aligned with declared environment variables
- Use full URLs where they simplify local and test ergonomics

---

## Eventing Boundary

Dapr is the app-facing eventing boundary. Application code may know Dapr pub/sub names, topics, CloudEvents, and outbox semantics. Application code must not know whether the runtime uses SNS/SQS, Redis, Kafka, or another broker. The durable application handoff is the database outbox.

---

## Delivery Shape — Review-First

- Build before deploy
- Plan before apply
- Use immutable image tags
- Emit release evidence for every cloud-changing workflow
- Keep deploy and apply triggers reviewed and intentionally separate
- Treat contract and runtime checks as first-class gates, not optional follow-up

---

## Adding a New Workload — Checklist

1. Add `apps/<name>/main.py`, `config.py`, and `pyproject.toml`
2. Add the workload to `platform/workloads.json` **before** adding runtime-specific infrastructure
3. Reuse the shared workload Dockerfile unless there is a real need not to
4. For services: expose `/health`, `/ready`, and `/metrics`
5. For jobs: emit structured success and progress events and document idempotency
6. Add focused pytest coverage and keep `make runtime-conformance` passing

---

## What Is Intentionally Not Here

Do not add these unless a real workload or operating need appears:
- Dapr state store, bindings, workflows, actors, or secrets
- A second cloud/runtime target
- Kubernetes, Helm, Kustomize, or Crossplane
- Generic provider-neutral infrastructure modules
- Analytics orchestration or data transformation stacks
- Hosted Grafana/Loki/Tempo/Prometheus runtime modules

---

## Quality Gates — Run Before Calling a Change Done

```bash
make lint                    # Ruff, Pyright, actionlint, hadolint, lychee
make secret-scan             # Gitleaks
make dependency-audit        # pip-audit
uv run pytest tests/ -v      # full test suite
make runtime-conformance     # external contract proof
```

For Terraform changes: `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed plan, separate apply.

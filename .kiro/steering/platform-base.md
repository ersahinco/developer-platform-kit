---
inclusion: always
---

# Platform Monorepo - Agent Base Rules

Always-on Kiro base rules for `aws-sdlc-containers`.

Short form: standardize the delivery workflow, do not replace the tools.

## Project Identity

Use these terms:

| Use | Avoid |
|---|---|
| delivery toolkit | framework, custom framework |
| workload | microservice |
| portable by boundary | cloud-neutral |
| platform edge | cloud abstraction layer |
| runtime target | cloud provider |

## Layer Ownership

| Path | Owns |
|---|---|
| `packages/domain/` | Entities, value objects, domain events; no provider SDKs, framework imports, or runtime details |
| `packages/application/` | Use cases, ports, workflow logic; no SQL, Dapr internals, or AWS SDK |
| `packages/infrastructure/` | SQLAlchemy, Dapr, S3, runtime adapters |
| `apps/*/` | Thin workload hosts: settings, routes, lifecycle, dependency assembly |
| `platform/workloads.json` | Workload identity, operational class, ports, config/secret names, portable expectations |
| `platform/concerns/` | Shared runtime capabilities |
| `infra/catalog/` | Reusable AWS building blocks |
| `infra/platform/` | Bootstrap, network, GitHub OIDC |
| `infra/app/` | RDS, ECS, ALB, jobs, messaging, observability wiring |
| `scripts/` | CI, release, operator, observability, data helpers |
| `tests/` | API, application, runtime, infrastructure, contract checks |
| `.github/workflows/` | CI gates, app build/deploy, infra plan/apply, security |
| `db/` | Liquibase changelog, bootstrap SQL, PgBouncer assets |

Dependency direction is inward only:

```text
apps/* -> packages/application -> packages/domain
apps/* -> packages/infrastructure
packages/infrastructure -> packages/application + packages/domain
```

Provider resource names belong at the platform edge, never in domain or
application code.

## Workload Contract

Workload classes in `platform/workloads.json`:

| Class | Description |
|---|---|
| `edge-service` | User-facing or externally routed HTTP service |
| `internal-service` | Long-running service without public edge ownership |
| `operator-job` | One-off task triggered manually or by CI/operator workflow |
| `scheduled-job` | Recurring task triggered by a scheduler |

Current mapping: `api` -> `edge-service`, `order_event_consumer` ->
`internal-service`, `backfill_worker` -> `operator-job`,
`data_export_job` -> `scheduled-job`.

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

## Metadata and Eventing

Metadata ownership:

1. `platform/workloads.json` - what the workload is
2. `platform/runtime-conformance.json` - local/CI fixture data only
3. `infra/app/workload_inventory.tf` - how AWS fulfills the contract

Do not turn `platform/workloads.json` into a deployment DSL.
Do not let `infra/app/workload_inventory.tf` redefine workload identity.
Do not let `platform/runtime-conformance.json` grow second application-spec semantics.

Eventing boundary:

- Dapr is the app-facing eventing boundary.
- Application code may know Dapr pub/sub names, topics, CloudEvents, and outbox semantics.
- Application code must not know whether runtime transport is SNS/SQS, Redis, Kafka, or another broker.
- The durable application handoff is the database outbox.

## Delivery and Change Rules

- Build before deploy.
- Plan before apply.
- Use immutable image tags.
- Emit release evidence for every cloud-changing workflow.
- Keep deploy and apply reviewed and separate.
- Treat contract and runtime checks as first-class gates.

Adding a workload:

1. Add `apps/<name>/main.py`, `config.py`, `pyproject.toml`.
2. Add the workload to `platform/workloads.json` before runtime-specific infrastructure.
3. Reuse the shared workload Dockerfile unless there is a real reason not to.
4. Services expose `/health`, `/ready`, `/metrics`.
5. Jobs emit structured events and document idempotency.
6. Add focused pytest coverage and keep `make runtime-conformance` passing.

Do not add without a real need:

- Dapr state store, bindings, workflows, actors, or secrets
- A second cloud/runtime target
- Kubernetes, Helm, Kustomize, or Crossplane
- Generic provider-neutral infrastructure modules
- Analytics orchestration or data transformation stacks
- Hosted Grafana/Loki/Tempo/Prometheus runtime modules

## Quality Gates

```bash
make lint
make secret-scan
make dependency-audit
uv run pytest tests/ -v
make runtime-conformance
```

For Terraform changes: `terraform fmt`, `terraform validate`, TFLint, Checkov,
reviewed plan, separate apply.

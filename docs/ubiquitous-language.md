# Ubiquitous Language

Use these terms in docs, tests, and code review. Goal: one small vocabulary.

Project sentence:

This project is an opinionated platform monorepo whose stable center is the
workload contract and the platform catalog. Runtime targets are pluggable
implementations at the platform edge.

Short form: standardize the delivery workflow, do not replace the tools.

## Core Terms

| Term | Meaning |
|---|---|
| delivery toolkit | repo conventions, contracts, scripts, tests, docs, and infrastructure shape; not a private framework |
| stable center | the long-lived platform meaning carried by the workload contract and platform catalog |
| workload | deployable or runnable unit under `apps/` |
| service workload | long-running HTTP workload with `/health`, `/ready`, `/metrics` |
| job workload | one-off or scheduled workload with meaningful exit status and structured lifecycle events |
| app host | runtime wiring in `apps/*`: settings, routes, lifecycle, dependency assembly |
| application core | business behavior in `packages/domain` and `packages/application` |
| infrastructure package | SQL, Dapr, storage, and runtime adapters in `packages/infrastructure` |
| platform catalog | reusable building blocks, templates, modules, policies, concerns, and delivery paths that realize workload needs |
| platform edge | Terraform, Dapr components, GitHub Actions, runtime-facing scripts, and infrastructure adapters |
| workload contract | canonical workload intent: image, config, secrets, health, telemetry, rollback, evidence, and tests |
| runtime target | hosting implementation such as `aws-ecs`, managed Kubernetes, jobs, or future data runtimes |
| portability by boundary | app contract and evidence shape travel; provider implementation stays isolated |
| conformance | executable proof that an implementation satisfies a contract |
| release evidence | Markdown, JSON, and JSONL records describing change, revision, verification, and alarms |
| operator evidence | logs, metrics, traces, release events, runbook outputs, and incident bundles |
| portable observability baseline | Prometheus metrics, Loki-compatible logs, optional OTLP/HTTP traces, Grafana dashboards |
| PostgreSQL-compatible contract | PostgreSQL semantics, Liquibase, PgBouncer, runtime secret injection, restore/forward-fix recovery |

## Use

| Say this | Not this |
|---|---|
| add a workload | add a microservice |
| add a runtime target | add a cloud abstraction layer |
| extend the platform catalog | build another internal framework |
| keep provider details at the platform edge | hide the cloud |
| satisfy the workload contract | match the framework |
| realize the contract | reinterpret workload intent per runtime |
| portable shape, provider-specific implementation | cloud-neutral implementation |
| delivery toolkit | custom framework |
| runtime target | cloud abstraction |
| portable by boundary | cloud-neutral |

## Placement Rules

- business behavior starts in `packages/domain` or `packages/application`
- runtime wiring starts in `apps/*`
- SQL, Dapr, object storage, and provider SDK code start in `packages/infrastructure` or platform/delivery edges
- workload metadata starts in `platform/workloads.json`
- shared runtime capability definitions start in `platform/concerns/`
- reusable runtime-target building blocks start in `infra/catalog/`
- new docs update the canonical owner instead of creating a parallel explanation

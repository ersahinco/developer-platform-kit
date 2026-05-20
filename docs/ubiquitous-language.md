# Ubiquitous Language

Use these terms in docs, tests, and code review. Goal: one small vocabulary.

Project sentence:

This project is an opinionated cloud-native delivery toolkit that standardizes
how teams build, observe, containerize, and deploy portable application
workloads using proven industry-standard tools.

Short form: standardize the delivery workflow, do not replace the tools.

## Core Terms

| Term | Meaning |
|---|---|
| delivery toolkit | repo conventions, contracts, scripts, tests, docs, and infrastructure shape; not a private framework |
| workload | deployable or runnable unit under `apps/` |
| service workload | long-running HTTP workload with `/health`, `/ready`, `/metrics` |
| job workload | one-off or scheduled workload with meaningful exit status and structured lifecycle events |
| app host | runtime wiring in `apps/*`: settings, routes, lifecycle, dependency assembly |
| application core | business behavior in `packages/domain` and `packages/application` |
| infrastructure package | SQL, Dapr, storage, and runtime adapters in `packages/infrastructure` |
| platform edge | Terraform, Dapr components, GitHub Actions, AWS-facing scripts, and infrastructure adapters |
| workload contract | portable surface for image, config, secrets, health, telemetry, rollback, evidence, and tests |
| runtime target | hosting implementation, currently `aws-ecs` |
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
| keep provider details at the platform edge | hide the cloud |
| satisfy the workload contract | match the framework |
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
- new docs update the canonical owner instead of creating a parallel explanation

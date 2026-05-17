# Ubiquitous Language

Use these terms when discussing, documenting, or changing the project. The goal
is a small vocabulary that keeps humans, tests, docs, and code generation
aligned.

## Project Sentence

This project is an opinionated cloud-native delivery toolkit that standardizes
how teams build, observe, containerize, and deploy portable application
workloads using proven industry-standard tools.

Short form: standardize the delivery workflow, do not replace the tools.

## Core Terms

| Term | Meaning |
|---|---|
| Delivery toolkit | The repo conventions, contracts, scripts, tests, docs, and infrastructure shape that make workloads repeatable. It is not a private framework. |
| Workload | A deployable or runnable unit under `apps/`: service, worker, scheduled job, or one-off job. |
| Service workload | A long-running HTTP workload that exposes `/health`, `/ready`, and `/metrics`. |
| Job workload | A one-off or scheduled workload that exits with a meaningful status and emits structured start/progress/success/failure events. |
| App host | Runtime wiring in `apps/*`: settings, HTTP schemas/routes, process lifecycle, and dependency assembly. |
| Application core | Business behavior in `packages/domain` and `packages/application`, kept free of provider/runtime details. |
| Infrastructure package | Concrete SQL, Dapr, storage, and runtime adapters in `packages/infrastructure`. |
| Platform edge | Provider/runtime-owned implementation such as Terraform, Dapr components, GitHub Actions, AWS-facing scripts, and infrastructure adapters. |
| Workload contract | The portable surface every workload must satisfy: image, config, secrets, health/readiness, metrics/logs/traces, rollback, evidence, and tests. |
| Runtime target | A hosting implementation, currently `aws-ecs`, that can run declared workloads. |
| Portability by boundary | The app contract and evidence shape travel; provider implementation stays isolated at platform edges. |
| Conformance | Proof that an implementation satisfies a contract from the outside, preferably in local/CI checks. |
| Release evidence | Markdown/JSON/JSONL records that describe what changed, what revision ran, what verification happened, and what alarms or checks were observed. |
| Operator evidence | Logs, metrics, traces, release events, runbook outputs, and incident bundles that help someone understand runtime behavior. |
| Portable observability baseline | Prometheus metrics, Loki-compatible logs, optional OTLP/HTTP traces, and Grafana dashboards without a provider-locked datasource. |
| PostgreSQL-compatible contract | The database contract: PostgreSQL semantics, Liquibase migrations, PgBouncer expectations, runtime secret injection, and restore/forward-fix recovery rules. |

## Use These Phrases

- "Add a workload" when creating a new service, worker, scheduled job, or
  one-off job.
- "Add a runtime target" when adding a new hosting implementation for a real
  operating need.
- "Keep provider details at the platform edge" when avoiding AWS/GitHub/Dapr
  component leakage into app/domain/application code.
- "Satisfy the workload contract" when checking images, config, health,
  telemetry, rollback, and evidence.
- "Portable shape, provider-specific implementation" when explaining why ECS,
  RDS, S3, SNS/SQS, and GitHub Actions are allowed but not the app contract.
- Say "delivery toolkit", not "custom framework".
- Say "runtime target", not "cloud abstraction".

## Avoid These Phrases

- "Framework" for this repo. Say "delivery toolkit" unless you are explicitly
  warning against framework behavior.
- "Cloud-neutral" for the current implementation. Say "portable by boundary."
- "Microservice" for every app folder. Say "workload" or "app host"; the current
  system is still a modular monolith with multiple workload hosts.
- "Generic abstraction layer" for provider portability. Say "platform edge" or
  "runtime target" and keep the standard tool visible.
- "AWS sandbox" as the primary identity. AWS/ECS is the current runtime
  implementation; the reusable value is the delivery workflow.

## Coding Rules Of Thumb

- New business behavior starts in `packages/domain` or `packages/application`.
- New runtime wiring starts in `apps/*`.
- New SQL, Dapr, object storage, or provider SDK code starts in
  `packages/infrastructure` or platform/delivery edges.
- New workload metadata starts in `platform/workloads.json`.
- New operator action belongs in a runbook only when someone can actually run
  it.
- New docs should update the canonical owner instead of creating a parallel
  explanation.

# Portability Status

This project is portable by boundary, not by pretending the current runtime is
cloud-neutral. The application core, local runtime, observability assets,
incident evidence, and delivery contracts are designed to travel. The deployed
sandbox intentionally uses AWS for managed runtime infrastructure and GitHub
Actions for orchestration.

## Portable Baseline

| Area | Status | Contract |
|---|---|---|
| Application core | Portable | `packages/domain` and `packages/application` stay free of AWS, Terraform, GitHub Actions, Grafana, Loki, Prometheus, Tempo, and OpenTelemetry imports. |
| App/platform contract | Portable shape | `docs/platform-contract.md` defines the workload contract for images, health/readiness/metrics, logs, traces, config, evidence, and rollback before adding another runtime target. |
| Runtime capability contract | Appendable shape | `docs/runtime-capability-contract.md`, `docs/runtime-addition-checklist.md`, and `platform/runtime-capabilities.json` define what a runtime target must provide for networking, identity, secrets, ingress, observability, jobs, rollout, rollback, evidence, cost controls, and Terraform ownership. |
| Workload onboarding | Portable shape | `docs/workload-onboarding-contract.md` defines the service/job files, health/readiness/metrics, logs, config/secrets, rollback, evidence, and tests required before runtime wiring. |
| Database portability | PostgreSQL-compatible shape | `docs/database-portability-contract.md` defines PostgreSQL, Liquibase, PgBouncer, backup/restore, and secret-injection expectations. RDS is the current AWS implementation, not the app contract. |
| Dapr eventing | Portable app boundary | `docs/dapr-portability-contract.md` keeps app eventing on Dapr pub/sub, CloudEvents, outbox, and idempotency semantics while SNS/SQS remains the current AWS component implementation. |
| Config and secrets | Portable shape | `docs/config-secrets-contract.md` defines env naming, secret separation, source by environment, and provider-edge config rules. |
| Observability onboarding | OSS app baseline | `docs/observability-onboarding-contract.md` defines Prometheus, Loki, Tempo, Grafana, release evidence, and incident query-hint expectations for new workloads. |
| CI quality gates | Portable delivery shape | `docs/ci-quality-contract.md` defines the reusable gate shape around ruff, pyright, pytest, contract validation, docs/workflow/Dockerfile checks, security scans, image scans, and Terraform checks. |
| Data/object storage | Portable data shape | `docs/data-object-storage-portability.md` defines dataset paths, manifest integrity, idempotent run IDs, write ordering, and provider SDK isolation. |
| Toolkit checklists | Portable shape | `docs/portable-toolkit-checklists.md` gives small onboarding checks for workloads, Dapr eventing, config/secrets, observability, CI quality gates, and object-storage/data hub behavior. |
| Runtime adapters | Mostly portable | `packages/infrastructure` owns SQL, Dapr, storage, and runtime adapters behind application ports. |
| Local runtime | Portable | `compose.yaml`, Dockerfiles, Liquibase, PgBouncer, Dapr local assets, and the Grafana OSS stack run without AWS. |
| Observability | Mostly OSS-portable | Grafana uses Prometheus, Loki, and Tempo. No Grafana Cloud AI or Grafana CloudWatch datasource is part of the baseline. |
| Incident evidence | Portable | Evidence bundles are Markdown/JSON and include query hints, release events, alarms, task definitions, image tags, and GitHub run IDs. |
| Rollback drills | Mostly portable | App and data rollback drills are GitHub Actions workflows plus app/runtime checks. Infra rollback remains reviewed Terraform plan/apply. |
| Delivery evidence | Portable shape, environment-dependent transport | Release events are artifacts everywhere and can be pushed to Loki when a reachable `LOKI_PUSH_URL` or `LOKI_URL` exists. |

## Intentional Provider Dependencies

| Provider | Why It Exists | Boundary |
|---|---|---|
| AWS | Runtime sandbox for ECS, RDS, ALB/WAF, ECR, S3, SNS/SQS, EventBridge Scheduler, CloudWatch alarms, Route 53, IAM, and VPC networking. | Contained in `infra/platform`, `infra/app`, AWS-facing scripts, and workflow credentials. |
| GitHub Actions | CI/CD orchestrator, review gates, image build/push, rollout drills, and Terraform plan/apply workflow. | Contained in `.github/workflows` and `scripts/ci`. |
| Terraform AWS provider | Reproducible platform/app infrastructure ownership. | Split roots under `infra/platform` and `infra/app`. |
| CloudWatch | AWS-native rollback alarms and managed-service signals. | Not used as a Grafana datasource; retained for ECS rollback and AWS-managed resources. |
| RDS | Current PostgreSQL runtime implementation. | Not exposed as the application database contract; app code uses PostgreSQL connection settings and SQLAlchemy infrastructure adapters. |

## Current Gaps

| Gap | Status | Next normal move |
|---|---|---|
| CI-to-Loki release-event publishing | Ready but not active | Configure a real `LOKI_PUSH_URL` on the GitHub `aws` environment through a private runner/network path or reviewed authenticated endpoint, then run `make release-event-delivery-verify`. |
| Metrics parity for AWS-managed resources | Partial | Keep CloudWatch alarms for ALB, RDS, SQS, Scheduler, WAF, and data-export freshness at the AWS platform edge until a deliberate exporter/ruler path exists. Do not make CloudWatch the application observability contract. |
| Trace routing abstraction | Partial | The API emits OTLP/HTTP directly to Tempo. Add an OpenTelemetry Collector only when there is a real need for routing, filtering, or multi-backend export. |
| Alternate runtime platform | Deferred but appendable | The app and runtime capability contracts are explicit, but no Kubernetes, Nomad, or second-cloud Terraform root exists. Add one only when there is a real operating requirement and it satisfies `platform/runtime-capabilities.json`. |
| Infra rollback drill workflow | Intentionally absent | Infra rollback stays reviewed `Infra Plan` plus `Infra Apply`; do not add a permanent infra rollback drill workflow. |

## Practical Status

The project is lean, pragmatic, and mostly OSS-portable at the application and
observability layers. The platform is intentionally AWS-specific, and the
delivery orchestrator is intentionally GitHub Actions. That is the useful
industry-standard split for this sandbox: app signals and evidence travel,
while provider-specific runtime ownership stays isolated and reviewable.

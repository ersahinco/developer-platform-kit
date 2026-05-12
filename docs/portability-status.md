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

## Current Gaps

| Gap | Status | Next normal move |
|---|---|---|
| CI-to-Loki release-event publishing | Ready but not active | Configure a real `LOKI_PUSH_URL` on the GitHub `aws` environment through a private runner/network path or reviewed authenticated endpoint, then run `make release-event-delivery-verify`. |
| Metrics parity for AWS-managed resources | Partial | Keep CloudWatch alarms for ALB, RDS, SQS, Scheduler, WAF, and data-export freshness until a deliberate exporter/ruler path exists. |
| Trace routing abstraction | Partial | The API emits OTLP/HTTP directly to Tempo. Add an OpenTelemetry Collector only when there is a real need for routing, filtering, or multi-backend export. |
| Alternate runtime platform | Deferred | The app layer is portable, but no Kubernetes, Nomad, or second-cloud Terraform root exists. Add one only when there is a real operating requirement. |
| Infra rollback drill workflow | Intentionally absent | Infra rollback stays reviewed `Infra Plan` plus `Infra Apply`; do not add a permanent infra rollback drill workflow. |

## Practical Status

The project is lean, pragmatic, and mostly OSS-portable at the application and
observability layers. The platform is intentionally AWS-specific, and the
delivery orchestrator is intentionally GitHub Actions. That is the useful
industry-standard split for this sandbox: app signals and evidence travel,
while provider-specific runtime ownership stays isolated and reviewable.

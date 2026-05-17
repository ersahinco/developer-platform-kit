# Runtime Toolkit

Use this when evaluating or adding a hosting runtime such as EKS, Azure, GCP,
Nomad, or cheaper compute. The goal is not multi-cloud ceremony. The goal is to
prove a real runtime can host the existing portable workloads without moving
provider assumptions into app code.

`docs/platform-contract.md` says what workloads must expose. This document says
what a runtime target must supply to run those workloads. Runtime guidance is
documentation-only while `aws-ecs` is the only target; add machine-readable
runtime metadata only when a second target exists and needs automated checks.

## Entry Criteria

- There is a concrete operating reason: lower cost, better workload fit,
  required managed capability, region/account constraint, or reliability need.
- `packages/domain` and `packages/application` do not need provider imports,
  Terraform knowledge, GitHub workflow knowledge, or runtime-specific settings.
- Existing workloads continue to satisfy `platform/workloads.json`; app
  contract changes are made only when every runtime should support the same new
  behavior.
- Provider-native observability is allowed for provider-managed infrastructure
  such as load balancers, databases, queues, schedulers, firewalls, and control
  planes. The app baseline remains Prometheus metrics, Loki-compatible logs,
  optional OTLP/HTTP traces through OpenTelemetry/ADOT, and Grafana dashboards
  without a provider-locked datasource requirement.

Do not add EKS, Azure, GCP, Nomad, or another target just to prove portability.
The target becomes useful when it can host real workloads cheaper, safer, or
with operational capabilities the current runtime cannot provide.

## Required Capabilities

Before a runtime is documented as supported, prove the following capabilities
with real owner/evidence paths:

| Capability | Runtime must provide |
| --- | --- |
| Container runtime | Run committed OCI images from `platform/workloads.json` with immutable revision naming, non-root execution, and workload command handling. |
| Networking | Public/private placement, dependency routing, egress, DNS, and how workloads reach databases, queues, object storage, and observability endpoints. |
| Identity | Short-lived delivery identity plus least-privilege runtime identity for services and jobs. |
| Secrets | Runtime secret injection into environment variables or mounted files, with no secret values in images, tfvars, logs, or release artifacts. |
| Ingress | External/internal routing, health and readiness semantics, TLS/WAF or equivalent edge controls, and failure behavior. |
| Observability | Prometheus-compatible metrics, Loki-compatible logs, OpenTelemetry-compatible OTLP/HTTP traces when enabled, and Grafana dashboards without provider-locked dashboards as the app baseline. |
| Jobs | One-off and scheduled job execution using the same image, config, secrets, structured events, idempotency, and evidence conventions. |
| Rollout | Immutable revision rollout with verification before declaring success. Provider-native rollout semantics are allowed, but evidence shape must stay portable. |
| Rollback | Separate app image rollback, runtime data rollback, infra rollback, and one-off job recovery categories. |
| Release evidence | Same Markdown/JSON/JSONL schema, with provider-native deployment IDs mapped into `runtime_id`, `workload_id`, `deployment_id`, `image_digest`, `rollback_category`, `source_workflow`, and `evidence_links`. |
| Cost controls | Explicit CPU/memory/replica/storage/placement levers that can be tuned without app changes. |
| Terraform ownership | Separate bootstrap/platform and app/runtime ownership, with reviewed plan/apply and no normal app image rollout owned by Terraform. |
| Local/CI guardrails | Contract validation, workflow checks, docs checks, Terraform formatting, and runtime-specific drift checks run before deploy. |

## Current AWS ECS Target

The current `aws-ecs` target is documented here and implemented through
`infra/`, `.github/workflows/`, `scripts/`, tests, docs, and `compose.yaml`.
The automated validator intentionally checks only `platform/workloads.json`
while there is one runtime; this avoids maintaining a second copy of the
runtime design in JSON.

This is deliberately not a cloud-neutral abstraction layer. AWS details remain
inside `infra/platform`, `infra/app`, AWS-facing scripts, and GitHub workflow
credentials. The portable part is the capability shape and evidence schema.

## Portable Baseline

This project is portable by boundary, not by pretending the current runtime is
cloud-neutral. The application core, local runtime, observability assets,
incident evidence, and delivery contracts are designed to travel. The deployed
sandbox intentionally uses AWS for managed runtime infrastructure and GitHub
Actions for orchestration.

| Area | Status | Contract |
|---|---|---|
| Application core | Portable | `packages/domain` and `packages/application` stay free of AWS, Terraform, GitHub Actions, Grafana, Loki, Prometheus, Tempo, and OpenTelemetry imports. |
| App/platform contract | Portable shape | `docs/platform-contract.md` defines workload images, health/readiness/metrics, logs, traces, config, eventing, evidence, and rollback before another runtime target is added. |
| Runtime toolkit | Appendable shape | This document defines what a runtime target must provide for networking, identity, secrets, ingress, observability, jobs, rollout, rollback, evidence, cost controls, and Terraform ownership. |
| Data and database | PostgreSQL-compatible shape | `docs/data.md` defines PostgreSQL, Liquibase, PgBouncer, backup/restore, secret injection, dataset paths, manifest integrity, idempotent run IDs, write ordering, and provider SDK isolation expectations. |
| Runtime adapters | Mostly portable | `packages/infrastructure` owns SQL, Dapr, storage, and runtime adapters behind application ports. |
| Local runtime | Portable | `compose.yaml`, Dockerfiles, Liquibase, PgBouncer, Dapr local assets, and the Grafana OSS stack run without AWS. |
| Observability | Mostly OSS-portable | Grafana uses Prometheus, Loki, and Tempo locally; ECS uses ADOT as the sidecar collector path. No Grafana CloudWatch datasource is part of the baseline. |
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
| Trace routing abstraction | Current | The API emits OTLP/HTTP to the same-task ADOT collector on ECS and directly to Tempo locally. Override the collector config when routing, filtering, or multi-backend export is needed. |
| Alternate runtime platform | Deferred but appendable | The app and runtime expectations are explicit, but no Kubernetes, Nomad, or second-cloud Terraform root exists. Add one only when there is a real operating requirement and it satisfies this document and `platform/workloads.json`. |
| Infra rollback drill workflow | Intentionally absent | Infra rollback stays reviewed `Infra Plan` plus `Infra Apply`; do not add a permanent infra rollback drill workflow. |

## Implementation Steps

1. Document the reason for the runtime and the expected operator benefit.
2. Choose explicit Terraform roots under `infra/` for bootstrap/platform and
   app/runtime ownership, then document what each root owns and does not own.
3. Implement runtime-specific networking, identity, secrets, ingress,
   observability, job, rollout, rollback, and cost controls at platform or
   delivery edges.
4. Keep app/domain/application code unchanged unless the portable workload
   contract itself needs a provider-neutral addition.
5. Add runtime roots first, prove their ownership boundaries, and keep root
   imports away from app internals.
6. Run `make runtime-conformance` against the declared workload images.
7. Emit the same release event artifacts from deploy, rollback, and infra apply
   paths.
8. Add machine-readable runtime metadata only after a second target exists and
   owner/evidence paths are real for every provider-neutral capability.
9. Run `uv run python scripts/ci/validate_platform_contract.py` and the normal
   contract/script/workflow/docs/Terraform checks before calling the runtime
   supported.

## Exit Criteria

- Declared workloads pass `scripts/ci/validate_platform_contract.py`.
- The runtime target has distinct bootstrap/platform and app/runtime roots under
  `infra/`, and those roots do not import workload app internals.
- Declared workload images pass `make runtime-conformance`.
- Incident timelines can follow deploy, rollback, infra apply, logs, metrics,
  traces, and job events without changing the evidence schema.
- Rollback drills still cover exactly app no-data rollback and data runtime
  rollback; infra rollback remains reviewed plan/apply.
- AWS, Kubernetes, Azure, GCP, or other provider names stay out of
  `packages/domain`, `packages/application`, and workload business behavior.

## Practical Status

The project is lean, pragmatic, and mostly OSS-portable at the application and
observability layers. The platform is intentionally AWS-specific, and the
delivery orchestrator is intentionally GitHub Actions. That is the useful
industry-standard split for this sandbox: app signals and evidence travel,
while provider-specific runtime ownership stays isolated and reviewable.

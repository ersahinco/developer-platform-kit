# Runtime Toolkit

Use this when evaluating or adding a hosting runtime such as EKS, Azure, GCP,
Nomad, or cheaper compute. The goal is not multi-cloud ceremony. The goal is to
prove a real runtime can host the existing portable workloads without moving
provider assumptions into app code.

`docs/platform-contract.md` says what workloads must expose. This document says
what a runtime target must supply to run those workloads. The machine-readable
runtime contract lives in `platform/runtime-capabilities.json`.

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

Before a runtime is documented as supported, declare every capability in
`platform/runtime-capabilities.json` and keep the listed owner/evidence paths
real:

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

`platform/runtime-capabilities.json` declares the current `aws-ecs` target and
points each capability at owner and evidence paths in `infra/`,
`.github/workflows/`, `scripts/`, `tests/`, docs, and `compose.yaml`. The
validator checks the runtime schema, current-target ownership, path existence,
and structured provider-neutral `provides` coverage for ingress, workload
identity, secret injection, config injection, logs, metrics, traces, deploy,
rollback, one-off jobs, object storage, and PostgreSQL connectivity.

This is deliberately not a cloud-neutral abstraction layer. AWS details remain
inside `infra/platform`, `infra/app`, AWS-facing scripts, and GitHub workflow
credentials. The portable part is the capability shape and evidence schema.

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
8. Add the target to `platform/runtime-capabilities.json` only after owner and
   evidence paths exist for every provider-neutral capability.
9. Run `uv run python scripts/ci/validate_platform_contract.py` and the normal
   contract/script/workflow/docs/Terraform checks before calling the runtime
   supported.

## Exit Criteria

- The runtime target passes `scripts/ci/validate_platform_contract.py`.
- The runtime target has distinct bootstrap/platform and app/runtime roots under
  `infra/`, and those roots do not import workload app internals.
- Declared workload images pass `make runtime-conformance`.
- Incident timelines can follow deploy, rollback, infra apply, logs, metrics,
  traces, and job events without changing the evidence schema.
- Rollback drills still cover exactly app no-data rollback and data runtime
  rollback; infra rollback remains reviewed plan/apply.
- AWS, Kubernetes, Azure, GCP, or other provider names stay out of
  `packages/domain`, `packages/application`, and workload business behavior.

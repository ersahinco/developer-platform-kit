# Future Runtime Addition Checklist

Use this checklist before adding EKS, Azure, GCP, Nomad, or any other hosting
target. The goal is not multi-cloud ceremony. The goal is to prove a real
runtime can host the existing portable workloads without moving provider
assumptions into app code.

## Entry Criteria

- There is a concrete operating reason: lower cost, better workload fit,
  required managed capability, region/account constraint, or reliability need.
- `packages/domain` and `packages/application` do not need provider imports,
  Terraform knowledge, GitHub workflow knowledge, or runtime-specific settings.
- Existing workloads continue to satisfy `platform/workloads.json`; app
  contract changes are made only when every runtime should support the same
  new behavior.
- Provider-native observability is allowed for provider-managed infrastructure
  such as load balancers, databases, queues, schedulers, firewalls, and control
  planes. CloudWatch is acceptable at the AWS platform edge for those signals;
  another runtime may have its own equivalent. The app baseline remains
  Prometheus metrics, Loki-compatible logs, optional OTLP/HTTP traces to Tempo,
  and Grafana dashboards without a provider-locked datasource requirement.

## Runtime Work

Before a target is documented as supported, prove every capability in
`platform/runtime-capabilities.json`:

| Capability | Decision or proof required |
| --- | --- |
| Container runtime | OCI image source, immutable revision naming, non-root execution, and workload command handling. |
| Networking | Public/private placement, dependency routing, egress, DNS, and how workloads reach databases, queues, object storage, and observability endpoints. |
| Identity | Delivery identity and runtime identity, including least-privilege roles/service accounts for services and jobs. |
| Secrets | Secret store, injection mechanism, rotation owner, and proof that images, tfvars, logs, and release artifacts do not contain secret values. |
| Ingress | External/internal routing, health and readiness semantics, TLS/WAF or equivalent edge controls, and failure behavior. |
| Observability | Metrics, logs, traces, dashboards, and any provider-native infra metrics kept at the runtime edge rather than the app contract. |
| Jobs | One-off and scheduled job execution using the same image, config, secrets, structured events, idempotency, and evidence conventions. |
| Rollout | Immutable rollout mechanism, verification step, failure detection, and release evidence emission before success is declared. |
| Rollback | App image rollback, runtime data rollback, infra rollback, and one-off job recovery remain separate categories. |
| Release evidence | Same Markdown/JSON/JSONL schema, with provider-native deployment IDs mapped into the existing revision/workflow/evidence fields. |
| Cost controls | Explicit CPU/memory/replica/storage/placement levers that can be tuned without app changes. |
| Terraform ownership | Separate bootstrap/platform and app/runtime ownership, with reviewed plan/apply and no normal app image rollout owned by Terraform. |
| Local/CI guardrails | Contract validation, workflow checks, docs checks, Terraform formatting, and runtime-specific drift checks run before deploy. |

## Implementation Steps

1. Document the reason for the runtime and the expected operator benefit.
2. Choose explicit Terraform roots under `infra/` for bootstrap/platform and
   app/runtime ownership, then document what each root owns and does not own.
3. Implement runtime-specific networking, identity, secrets, ingress,
   observability, job, rollout, rollback, and cost controls at platform or
   delivery edges.
4. Keep app/domain/application code unchanged unless the portable workload
   contract itself needs a provider-neutral addition.
5. Emit the same release event artifacts from deploy, rollback, and infra apply
   paths.
6. Add the target to `platform/runtime-capabilities.json` only after proof files
   and required tokens exist.
7. Run `uv run python scripts/ci/validate_platform_contract.py` and the normal
   contract/script/workflow/docs/Terraform checks before calling the runtime
   supported.

## Exit Criteria

- The runtime target passes `scripts/ci/validate_platform_contract.py`.
- Incident timelines can follow deploy, rollback, infra apply, logs, metrics,
  traces, and job events without changing the evidence schema.
- Rollback drills still cover exactly app no-data rollback and data runtime
  rollback; infra rollback remains reviewed plan/apply.
- AWS, Kubernetes, Azure, GCP, or other provider names stay out of
  `packages/domain`, `packages/application`, and workload business behavior.

# Runtime Capability Contract

This contract defines what a hosting runtime must provide before this repo calls
it supported. It is intentionally separate from the portable app contract:
`docs/platform-contract.md` says what workloads must expose, while this document
says what a runtime target must supply to run those workloads.

The current runtime target is `aws-ecs`. Future targets such as EKS, Azure, or
GCP should be appended only when there is a real operating need. They must
satisfy `platform/runtime-capabilities.json` without changing app/domain code.

## Required Capabilities

| Capability | Runtime must provide |
| --- | --- |
| Container runtime | Run the committed OCI images from `platform/workloads.json` without changing app code. |
| Networking | Isolated network, public and private placement, database/data-plane placement, and clear routing between workloads and dependencies. |
| Identity | Short-lived delivery identity plus least-privilege runtime identity for services and jobs. |
| Secrets | Runtime secret injection into environment variables or mounted files, with no secret values in images, tfvars, or logs. |
| Ingress | Public or internal ingress that routes to workload `/health` and `/ready` semantics and supports the app metrics/log/tracing contract. |
| Observability | Prometheus-compatible metrics, Loki-compatible logs, Tempo-compatible OTLP/HTTP traces when enabled, and Grafana dashboards without provider-locked dashboards as the app baseline. |
| Jobs | One-off and scheduled workload execution with the same image, config, secret, logging, idempotency, and evidence conventions as services. |
| Rollout | Immutable revision rollout with verification before declaring success. Provider-native rollout semantics are allowed, but evidence shape must stay portable. |
| Rollback | Separate app image rollback, runtime data rollback, infra rollback, and one-off job recovery categories. |
| Release evidence | Markdown/JSON/JSONL release events with the same schema across runtimes. Provider-native revision IDs map into the existing revision fields until a second runtime proves a better common name is needed. |
| Cost controls | Explicit sizing, replica, storage, and placement controls that operators can tune without app changes. |
| Terraform ownership | Bootstrap/platform ownership and app/runtime ownership stay separate. Runtime-specific Terraform must not take over app image rollout ownership. |
| Local/CI guardrails | Local and CI checks catch drift in app contract, runtime contract, workflows, docs, Terraform formatting, and release evidence before deploy. |

## Current AWS ECS Target

`platform/runtime-capabilities.json` declares the current `aws-ecs` target and
points each capability at proof files in `infra/`, `.github/workflows/`,
`scripts/`, `tests/`, docs, and `compose.yaml`. The validator checks that each
capability has proof files and expected tokens.

This is deliberately not a cloud-neutral abstraction layer. AWS details remain
inside `infra/platform`, `infra/app`, AWS-facing scripts, and GitHub workflow
credentials. The portable part is the capability shape and evidence schema.

## Adding A Runtime Later

Use `docs/runtime-addition-checklist.md` before adding a runtime target. To add
a runtime target later:

1. Keep app/domain/application code unchanged.
2. Add a new runtime target to `platform/runtime-capabilities.json`.
3. Implement every required capability at platform/delivery edges.
4. Reuse `platform/workloads.json` and the existing release evidence schema.
5. Add Terraform ownership docs and reviewed plan/apply boundaries.
6. Add local/CI validation before declaring the runtime supported.

Do not add the target to `platform/runtime-capabilities.json` until its proof
files and required tokens exist. Future Terraform roots may be runtime-specific,
but they must stay explicit under `infra/` and preserve separate
bootstrap/platform and app/runtime ownership.

Do not add EKS, Azure, GCP, Nomad, or another target just to prove portability.
The target becomes useful when it can host real workloads cheaper, safer, or
with operational capabilities the current runtime cannot provide.

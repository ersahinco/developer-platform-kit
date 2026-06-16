# Proof Ladder

The delivery toolkit proves workloads in a small ladder:

```text
static contracts -> local Compose -> local Kubernetes evidence drill -> AWS ECS evidence
```

Each rung should answer a different question. Move up only when the lower rung
cannot prove the boundary you care about.

| Rung | Use it for | Primary commands | Owner |
|---|---|---|---|
| Static contracts | Workload shape, runtime support/admission, docs links, policy, and manifest contracts | `make workload-readiness`, `make local-kubernetes-contracts`, `make runtime-conformance` | `platform/`, `tests/contracts/`, `tests/runtime/` |
| Local Compose | Fast app host proof with local database, Dapr, jobs, runtime fixtures, isolated live proof, and optional observability | `make dev`, `make local-app-up`, `make platform-toolkit-smoke-local`, `make local-compose-live-proof`, `make local-up` | `compose.yaml`, `platform/runtime-conformance.json`, `scripts/platform/local_compose_live_proof.py` |
| Local Kubernetes evidence drill | Local proof for Services, probes, Jobs, ConfigMaps, Secrets, service identity, rollout/rollback, Dapr sidecar wiring, endpoints, logs, and events | `make local-kubernetes-evidence-drill`, `make local-kubernetes-rollout-proof`, `make local-kubernetes-admission-report` | `infra/local-kubernetes/`, `scripts/platform/local_kubernetes/` |
| AWS ECS evidence | Reviewed production runtime proof with immutable images, IAM, ALB/WAF, RDS, SNS/SQS behind Dapr, S3, scheduled jobs, CloudWatch, and release evidence | `make platform-toolkit-validate-cloud`, `make release-evidence-runs`, `make operational-snapshot-cloud` | `.github/workflows/`, `infra/app/`, `scripts/observability/` |

## Change-To-Proof Map

Start with the cheapest proof that covers the boundary changed. Move up the
ladder only when that proof cannot see the risk.

| Change kind | Start with | Move up when |
|---|---|---|
| Workload metadata, owner, ports, config, secrets, class, or use cases | `make workload-readiness`, `make workload-readiness-check` | A runtime target must prove the declared boundary live |
| App host routes, settings, package wiring, health, readiness, metrics, logs, auth, local observability, or job exit behavior | `make platform-toolkit-smoke-local`, `make runtime-conformance` | Isolated live Compose evidence is needed: `make local-compose-live-proof`; or the change needs cloud readiness checks |
| Dapr pub/sub, outbox, CloudEvents, consumer idempotency, or async sidecar behavior | `make dapr-smoke`, `make platform-toolkit-smoke-local` | Kubernetes sidecar wiring, service identity, or runtime injection is the risk |
| Local Kubernetes manifests, probes, Jobs, ConfigMaps, Secrets, Services, sidecars, rollout, or rollback | `make local-kubernetes-contracts`, `make local-kubernetes-admission-report` | Live kind evidence is needed: `make local-kubernetes-evidence-drill` or `make local-kubernetes-rollout-proof` |
| GitHub workflow inputs, dry-run commands, delivery gates, Terraform readiness, or cloud evidence scripts | `make workflow-dry-run-validate`, `make platform-toolkit-validate-cloud` | A reviewed cloud-changing workflow is ready to run |
| Operator docs, release evidence, incident evidence, or runbooks | `uv run pytest tests/contracts/test_documented_make_targets.py tests/contracts/test_operator_docs_contract.py -q` | Cloud artifacts or runtime state must be inspected with `make release-evidence-runs` or `make operational-snapshot-cloud` |

## How To Use It

- Start with static contracts when reviewing metadata, catalog, candidate, or
  helper changes.
- Use local Compose for the default inner loop and fast workload behavior proof.
- Use `make local-compose-live-proof` when the risk is the local runtime
  boundary itself: token auth, health, readiness, metrics, structured logs, or
  local observability in an isolated Compose project.
- Use local Kubernetes only when Compose is too small to prove runtime
  boundaries such as Services, probes, rollout/rollback, Jobs, sidecars, and
  runtime injection.
- Use AWS ECS evidence only for cloud-changing delivery, production runtime
  readiness, or operator proof.

## Boundaries

Local Kubernetes is an active local proof runtime target, not production
Kubernetes. It stays static, kind-based, and limited to selected proof
workloads. Do not add Helm, CRDs, portals, app generators, enterprise
integrations, provider abstraction layers, or new runtime targets to climb this
ladder.

The workload contract stays the stable center. Runtime targets realize the
contract at the platform edge; they do not redefine workload identity or own
deployment choreography.

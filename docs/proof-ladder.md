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
| Local Compose | Fast app host proof with local database, Dapr, jobs, runtime fixtures, and optional observability | `make dev`, `make local-app-up`, `make platform-toolkit-smoke-local`, `make local-up` | `compose.yaml`, `platform/runtime-conformance.json` |
| Local Kubernetes evidence drill | Local proof for Services, probes, Jobs, ConfigMaps, Secrets, service identity, rollout/rollback, Dapr sidecar wiring, endpoints, logs, and events | `make local-kubernetes-evidence-drill`, `make local-kubernetes-rollout-proof`, `make local-kubernetes-admission-report` | `infra/local-kubernetes/`, `scripts/platform/local_kubernetes/` |
| AWS ECS evidence | Reviewed production runtime proof with immutable images, IAM, ALB/WAF, RDS, SNS/SQS behind Dapr, S3, scheduled jobs, CloudWatch, and release evidence | `make platform-toolkit-validate-cloud`, `make release-evidence-runs`, `make operational-snapshot-cloud` | `.github/workflows/`, `infra/app/`, `scripts/observability/` |

## How To Use It

- Start with static contracts when reviewing metadata, catalog, candidate, or
  helper changes.
- Use local Compose for the default inner loop and fast workload behavior proof.
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

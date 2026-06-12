# Local Kubernetes Runtime

`infra/local-kubernetes/` is the lean local Kubernetes proof runtime.

It uses `kind` plus `kubectl apply -k` to prove richer runtime boundaries than
Compose can show on its own: Services, probes, config and secret injection,
storage claims, job execution, service identity, and in-cluster dependency
connectivity.

This is not a cloud Kubernetes implementation, Helm chart, CRD surface, or
platform control plane. Keep it small and static. Add workload manifests here
only when a real local proof need exists and the workload already declares
`local-kubernetes` in `platform/workloads.json`.

## Commands

```bash
make local-kubernetes-doctor
make local-kubernetes-validate
make local-kubernetes-rollout-proof
make local-kubernetes-dapr-proof
make local-kubernetes-evidence-drill
make local-kubernetes-evidence-bundle
make local-kubernetes-admission-report
make local-kubernetes-down
```

`make local-kubernetes-validate` builds the required local images, creates or
reuses a kind cluster, loads the images, applies the manifests, waits for API
and event-consumer readiness, checks `/health`, `/ready`, and `/metrics`,
verifies proof jobs, proves Dapr event delivery, and then deletes the cluster.

`make local-kubernetes-rollout-proof` exercises the API Deployment with a second
immutable local image tag, waits for rollout readiness, probes `/health`,
`/ready`, and `/metrics`, rolls back to the previous revision, and writes local
JSON/Markdown evidence under `/tmp/aws-sdlc-containers-local-kubernetes-evidence`.

`make local-kubernetes-dapr-proof` creates an order through the API and waits
for the event consumer to receive the CloudEvent through its local daprd sidecar
and Redis-backed pub/sub component.

`make local-kubernetes-evidence-drill` is the repeatable local evidence drill:
it creates kind, runs validation plus Dapr proof, captures JSON/Markdown
evidence, and cleans up. It is an on-demand proof command, not a scheduler or CI
deployment workflow.

`make local-kubernetes-evidence-bundle` captures pods, deployments, services,
jobs, endpoints, events, API rollout status, API logs, event-consumer and daprd
logs, Redis logs, proof-job logs, and the static admission report for the
current kind cluster.

`make local-kubernetes-admission-report` is static. It explains which declared
workloads are ready for `local-kubernetes` support and why the rest are not.

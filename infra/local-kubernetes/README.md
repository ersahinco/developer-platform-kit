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
make local-kubernetes-down
```

`make local-kubernetes-validate` builds the required local images, creates or
reuses a kind cluster, loads the images, applies the manifests, waits for API
readiness, checks `/health`, `/ready`, and `/metrics`, verifies proof jobs, and
then deletes the cluster.

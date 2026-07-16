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

Use [Local Development](../../docs/local-development.md) for the developer
command journey and [Proof Ladder](../../docs/proof-ladder.md) for when to use
this runtime target.

## Manifest Ownership

`kubectl apply -k infra/local-kubernetes` is the stable entrypoint. The files are
split by concern so ownership stays visible:

| File | Owns |
|---|---|
| `namespace.yaml` | local namespace boundary |
| `runtime-db.yaml` | ServiceAccount, shared ConfigMap/Secret placeholders, PVCs, Postgres, PgBouncer, Liquibase |
| `runtime-eventing.yaml` | Redis plus Dapr config/component ConfigMaps |
| `workload-services.yaml` | API and event-consumer Deployments/Services, probes, service identity, runtime labels |
| `workload-jobs.yaml` | backfill, data export, operational snapshot, and integration check Jobs |

## Maintenance Rules

- Keep manifests static and readable; do not add Helm, CRDs, operators, or a
  provider abstraction layer.
- Add `local-kubernetes` support only after the workload has a real proof need,
  a manifest, injected declared config/secrets, and passing admission output.
- Keep workload identity in `platform/workloads.json`; manifests realize it but
  do not redefine it.
- The current Kubernetes Dapr proof covers pub/sub. Add another building block
  when its workload declares `local-kubernetes` support and the drill captures
  its failure mode and evidence.
- Keep evidence capture as an on-demand local artifact, not a scheduler or
  permanent drill workflow.

## Command Surface

```bash
make local-kubernetes-contracts
make local-kubernetes-admission-report
make local-kubernetes-evidence-drill
make local-kubernetes-rollout-proof
```

The command explanations live in local development docs. This README owns what
the manifests mean and what they must not grow into.

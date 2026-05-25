# Managed Kubernetes Catalog

This directory is reserved for reusable managed-Kubernetes runtime-target
modules when a real workload needs them.

Rules:

- Keep workload meaning in `platform/workloads.json` and `platform/concerns/`
- Keep target-specific realization here, not in the workload contract
- Do not add ArgoCD, Helm/Kustomize packaging, or cluster-control-plane
  assumptions unless managed Kubernetes becomes a repeated runtime target with a
  clear operator need

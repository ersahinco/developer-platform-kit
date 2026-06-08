# Local Kubernetes Catalog

`infra/catalog/local-kubernetes/` documents reusable local Kubernetes runtime
building blocks. These entries help developers prove workload boundaries with
Kubernetes Services, probes, jobs, config, secrets, and storage before any cloud
Kubernetes or owned substrate runtime is introduced.

Use this catalog when Compose is too small to prove a workload boundary. Keep it
static and standard-tool based: `kind`, `kubectl`, and Kubernetes manifests.
Do not add Helm, CRDs, operators, or cloud-specific Kubernetes resources here.

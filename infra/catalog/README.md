# Infrastructure Catalog

`infra/catalog/` is the extraction boundary for reusable runtime-target building
blocks.

Do not force module creation for its own sake. Extract into the catalog only
when a cloud primitive or runtime pattern is stable enough to reuse without
hiding the underlying standard tool.

Growth rule:

- Organize the catalog by runtime target under `infra/catalog/<runtime-target>/`
- Keep shared workload meaning in `platform/`; do not move contract semantics into catalog modules
- Use catalog YAML to describe reusable building blocks that examples and workloads can consume locally or in a runtime target
- Keep use-case-specific names, datasets, business events, and schema semantics out of catalog metadata
- Reserve `infra/catalog/managed-kubernetes/` for future managed-Kubernetes modules when a real workload needs them
- Reserve `infra/catalog/managed-service-provider/` for future managed provider-edge modules when a real workload needs hybrid database, DNS, edge, identity, or storage integration

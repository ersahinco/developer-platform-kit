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
- Describe, check, or explain boundaries only; do not create app code, redefine workload identity, own deployment choreography, or become a hidden framework
- Keep use-case-specific names, datasets, business events, and schema semantics out of catalog metadata
- Add a new runtime-target catalog branch only when a real workload needs it and the owner is clear

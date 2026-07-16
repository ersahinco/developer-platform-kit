# Infrastructure Catalog

`infra/catalog/` is the extraction boundary for reusable runtime-target building
blocks.

`capability-realizations.yaml` is the discovery surface for explicit provider
choices. It records stable IDs, ownership, maturity, inputs, secret names,
outputs, failure modes, evidence, and limits. It is inventory only: it is not a
composer, generator, or deployment manifest.

Do not force module creation for its own sake. Extract into the catalog only
when a cloud primitive or runtime pattern is stable enough to reuse without
hiding the underlying standard tool.

Growth rule:

- Keep runtime building blocks under `infra/catalog/<runtime-target>/`
- Keep provider choices in the root capability-realization inventory
- Keep shared workload meaning in `platform/`; do not move contract semantics into catalog modules
- Use catalog YAML to describe reusable building blocks that examples and workloads can consume locally or in a runtime target
- Describe, check, or explain boundaries only; do not create app code, redefine workload identity, own deployment choreography, or become a hidden framework
- Keep use-case-specific names, datasets, business events, and schema semantics out of catalog metadata
- Incubate a new runtime-target catalog branch before broad demand only with a concrete proof, owner, contract input, tests, evidence path, and honest maturity
- Add active runtime defaults and deploy roots only after reviewed realization

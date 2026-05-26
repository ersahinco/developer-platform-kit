# Managed Service Provider Catalog

This directory is reserved for reusable provider-edge building blocks when a
real workload needs managed PostgreSQL, DNS, edge, identity, or storage
integration for cost or hybrid design reasons.

Rules:

- Keep workload identity and admission in `platform/workloads.json`
- Keep provider-edge realization here, not in `packages/domain` or `packages/application`
- Prefer generic provider-edge building blocks before naming a specific vendor
- Do not imply that a provider edge is a full reviewed runtime target until it has a real owner and delivery path

# Workload Hosts

`apps/` contains runnable workload hosts.

Each folder reads settings, wires concrete dependencies, exposes routes or a
job entrypoint, and emits workload-level operational events.

Keep business behavior in `packages/`.

Rules:

- real workloads stay in `apps/` even when they only support `local-compose`
- `apps/` workloads should have contract metadata, tests, local proof, and an owner
- `examples/` is only for teaching, demo, and reference material

Example:

- `packages/application/data_export.py` -> export use case
- `packages/infrastructure/data_export.py` -> SQL, file, S3 adapters
- `apps/data_export_job/` -> runnable host
- `apps/operational_snapshot_job/` -> read-only operational readiness snapshot

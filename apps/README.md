# Workload Hosts

`apps/` contains runnable workload hosts.

Each folder reads settings, wires concrete dependencies, exposes routes or a
job entrypoint, and emits workload-level operational events.

Keep business behavior in `packages/`.

Example:

- `packages/application/data_export.py` -> export use case
- `packages/infrastructure/data_export.py` -> SQL, file, S3 adapters
- `apps/data_export_job/` -> runnable host

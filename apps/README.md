# Workload Examples

`apps/` contains reference workload hosts.

Each folder under `apps/` is the runnable host for one workload example:

- reads runtime settings
- assembles concrete dependencies
- exposes HTTP routes or a job entrypoint
- emits workload-level operational events

Keep business behavior out of `apps/` when it can live in `packages/`.

## Why `apps/` and `packages/` can sound similar

The names can overlap because they represent different layers, not duplicate
features.

Example: data export

- `packages/application/data_export.py` defines the export request, manifest,
  and core export workflow
- `packages/infrastructure/data_export.py` knows how to read rows from SQL,
  write files, and publish to S3
- `apps/data_export_job/` is the runnable workload host that reads settings,
  assembles the concrete reader/store/publisher, and executes the export job

If two files share a domain name such as `data_export`, that is acceptable when
one is application behavior and the other is the workload host that runs it.

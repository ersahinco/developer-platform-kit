# Workload Hosts

`apps/` contains runnable workload hosts.

Each folder reads settings, wires concrete dependencies, exposes routes or a
job entrypoint, and emits workload-level operational events.

Keep shared domain and application behavior in `packages/`. Keep workload-local
implementation details inside the workload until reuse is proven.

Rules:

- real workloads stay in `apps/` even when they only support `local-compose`
- `apps/` workloads should have contract metadata, tests, local proof, and an owner
- `examples/` is only for teaching, demo, and reference material

Examples:

- `packages/application/data_export.py` -> export use case
- `packages/infrastructure/data_export.py` -> SQL, file, S3 adapters
- `apps/data_export_job/` -> runnable host
- `apps/operational_snapshot_job/` -> read-only operational readiness snapshot
- `apps/integration_check_job/` -> configured HTTP integration check job
- `apps/lake_orders_ingest_job/` -> local-first Parquet/DuckDB data job
- `apps/churn_prediction_api/` -> local-first internal model inference app host
- `apps/support_triage_llm/` -> local-first internal LLM triage app host

Use `make workload-readiness` for the current complete workload inventory.

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

## Enterprise Pattern Experiments

Experimental workloads may precede broad product demand when they prove a
named engineering problem with an owner, workload contract, executable tests,
and inspectable evidence. They remain local-only until runtime admission is
reviewed.

| Workload | Proof |
|---|---|
| `booking_api` | Dapr service invocation reaches a workload whose PostgreSQL uniqueness invariant allows exactly one winner for concurrent attempts on the same resource and time slot |
| `lake_orders_ingest_job` | replayable projection rebuild deduplicates updates, flags late arrivals, and records source/model/output hashes |
| `churn_model_train_job` | versioned artifact records training-data lineage, evaluation scope, drift summary, and promotion decision |
| `churn_prediction_api` | inference rejects incompatible or unpromoted artifacts and reports the model identity used for each prediction |

Run the application and data pattern tests with `make enterprise-pattern-proofs`.
Run `make dapr-up dapr-smoke` for the live Dapr service-invocation path.

Use `make workload-readiness` for the current complete workload inventory.

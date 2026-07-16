# Workload Observability

Small contract for logs, metrics, terminal job events, and operator evidence.

## Services

Expose:

- `/health`
- `/ready`
- `/metrics`

`/metrics` must include Prometheus text and a stable workload identity sample:

```text
workload_info{workload="<workload-name>",workload_class="<operational-class>"} 1
```

Structured request logs must include:

- `workload`
- `event`
- `status`
- `request_id`

Use:

```bash
make api-smoke
make post-deploy-verify
```

## Jobs

Job logs must include a clear terminal event. The terminal event must include:

- `workload`
- `event`
- `status`
- `timestamp`
- `run_id` when the job uses run-id idempotency
- `mode` when the operator needs to know the execution posture

Examples:

- `backfill_complete`
- `data_export_succeeded`
- `integration_check_succeeded`
- `operational_snapshot_succeeded`
- `lake_orders_ingest_succeeded`
- `churn_model_train_succeeded`

Use:

```bash
make operational-snapshot
make integration-check
make data-export
make enterprise-pattern-proofs
```

## Operator Payloads

Operator payload artifacts use the same terminal event shape and add the final
artifact path:

- `workload`
- `event`
- `run_id`
- `mode`
- `timestamp`
- `status`
- `evidence_path`

Use:

```bash
make operational-snapshot-cloud
GH_RUN_ID=<workflow-run-id> make operator-payload-download
```

## External Backends

Datadog and Splunk can satisfy workload observability without app code changes
when the platform edge preserves the workload contract:

- Prometheus-compatible metrics include `workload_info` with stable workload
  identity.
- Structured logs preserve `workload`, `event`, `status`, `timestamp`, and
  request or run correlation fields.
- Release evidence, operator payloads, and incident evidence preserve workload
  id, run id, image tag, timestamp, status, and runtime identifiers.

Backend-specific collectors, indexes, sources, account routing, and API tokens
stay outside `platform/workloads.json`.

Langfuse, OpenTelemetry Collector, Grafana, Datadog, or Splunk routing can be
attached at the runtime edge when needed. Workload metadata still declares only
portable intent, config names, service endpoints, and metrics names.

## Runtime Conformance Probes

`platform/runtime-conformance.json` may include service probes for local/CI
runtime evidence. These probes are fixture data only: request method, path,
payload, expected status, response field presence, and structured log field
presence. App-specific behavior and domain semantics stay in app and contract
tests, not in runtime fixture metadata.

## Checks

Run the contract and local verification path:

```bash
uv run pytest tests/contracts/test_workload_observability_contract.py -q
make api-smoke
make integration-check
make post-deploy-verify
```

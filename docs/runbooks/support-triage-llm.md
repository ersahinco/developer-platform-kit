# Support Triage LLM Evidence

Use when `support_triage_llm` is not ready, triage output looks wrong, an
evaluation run fails, or a failed-run operator payload needs review.

## Local Checks

Start the local LLM workload:

```bash
docker compose --profile llm up support-triage-llm
```

Check readiness and metrics:

```bash
curl --fail --show-error http://127.0.0.1:8083/ready
curl --fail --show-error http://127.0.0.1:8083/metrics
```

Run a deterministic triage request:

```bash
curl --fail --show-error \
  -H "Content-Type: application/json" \
  --data '{"ticket_id":"T-runbook","subject":"Production API is down","body":"Checkout is unavailable","customer_tier":"enterprise","run_id":"runbook-triage"}' \
  http://127.0.0.1:8083/triage
```

Run evaluation evidence:

```bash
curl --fail --show-error \
  -H "Content-Type: application/json" \
  --data '{"run_id":"runbook-eval"}' \
  http://127.0.0.1:8083/evaluate
```

## Evidence

Local artifacts are written under the Compose `data_exports` volume:

- `support_triage_llm/runs/<run-id>.json`
- `support_triage_llm/evaluations/<run-id>.json`
- `support_triage_llm/operator-payloads/<run-id>.json`

Inspect artifacts:

```bash
make data-artifacts-list
make data-artifacts-shell
```

## What To Check

- `prompt_version` matches the expected prompt.
- `run_id` is preserved across logs, response, and evidence files.
- `token_evidence`, `estimated_cost_usd`, and `latency_ms` are present.
- Evaluation evidence has expected `case_count`, `passed_count`, and
  `failed_count`.
- Failed runs produce an operator payload with `status: failed`, `mode:
  operator_payload`, and `evidence_path`.

## Boundaries

Langfuse or another LLM observability backend may be attached at the runtime
edge later. Do not add backend-specific routing, project IDs, API tokens, or
trace destinations to `platform/workloads.json`.

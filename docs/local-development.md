# Local Development

Canonical local setup and day-to-day runbook.

Use [Architecture](architecture.md) for ownership rules and
[Platform Contract](platform-contract.md) for portable workload rules.
Local development is a first-class runtime target for this platform monorepo:
it should be fast, contract-faithful, and provider-light so engineers can
iterate before touching cloud infrastructure.

Use the live workload contract when you need the current inventory:

```bash
make workload-readiness
make workload-addition-report
```

Local-only workloads still belong in `apps/` when they have a real contract,
local proof, and owner. Reserve `examples/` for teaching, demo, and
reference-only samples.

## Preferred Setup

Prefer the dev container. Native host setup is fine with Docker Desktop,
Python 3.14+, and `uv`.

Key entrypoints:

- `compose.yaml`
- `infra/local-kubernetes/`
- `Makefile`
- `pyproject.toml`
- `uv.lock`
- `.devcontainer/`

## Workstation Bootstrap

Keep the host setup boring. A native macOS shell needs Docker Desktop running,
`kind`, `kubectl`, Python 3.14, and `uv`. If tools are installed with
Homebrew but not visible to Make, start the shell with:

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
```

Then prove the workstation before chasing runtime behavior:

```bash
make local-kubernetes-doctor
make local-kubernetes-contracts
make local-kubernetes-validate
make lint-policy
make lint-docs
```

`local-kubernetes-contracts` is the fast static check used by CI.
`local-kubernetes-validate` is the live proof. Success means Docker daemon
access works, kind can create a local cluster, static Kubernetes manifests
satisfy the workload contract, policy checks run, and docs links resolve. If a
command fails before reaching Kubernetes, fix the toolchain first; if it fails
inside the cluster, inspect the workload evidence.

Git hooks are active for commit and push. Install them from the repo-managed
toolchain, not from a global Python:

```bash
uv run pre-commit install
```

Use `make pre-commit` when you want to install hooks and run the full hook set
against the current tree.

## Standard Local Flow

```bash
make platform-doctor
make dev
make migrate
make seed
make local-up
curl --fail --show-error http://127.0.0.1:8000/health
```

Use stepwise Docker commands only when you intentionally want the API without
the full local profile.

`make platform-doctor` checks local tools, Docker daemon access, GitHub auth,
expected repo files, and workload readiness. It is a human diagnostic, not a CI
gate.

## Local Kubernetes Proof

Use local Kubernetes when Compose is too small to prove network, storage,
compute, probes, jobs, service identity, or config/secret injection. The active
local Kubernetes target uses `kind` and static manifests only.

```bash
make local-kubernetes-doctor
make local-kubernetes-validate
make local-kubernetes-rollout-proof
make local-kubernetes-dapr-proof
make local-kubernetes-evidence-drill
make local-kubernetes-admission-report
make local-kubernetes-down
```

This proves the API, event consumer, backfill worker, data export job,
operational snapshot job, and integration check job against Postgres, PgBouncer,
Liquibase, Redis, Dapr sidecar wiring, Services, probes, Secrets, ConfigMaps,
and PersistentVolumeClaims. It is not cloud Kubernetes, Helm, CRDs, or a
platform control plane.

Use `make local-kubernetes-rollout-proof` when you want the closest local proof
to production rollout behavior without adding a new runtime target. It creates a
kind cluster, applies the static manifests, rolls the API Deployment to a second
immutable local image tag, verifies `/health`, `/ready`, and `/metrics`, rolls
back, and writes local evidence.

Use `make local-kubernetes-dapr-proof` when you need proof that the existing
Dapr pub/sub workload boundary works in kind. It creates an order through the
API, lets the event consumer relay through its local daprd sidecar and Redis
component, and waits for the consume log evidence.

Use `make local-kubernetes-evidence-drill` as the repeatable local runtime
evidence drill. It creates the kind cluster, runs validation plus Dapr proof,
captures evidence, and cleans up without adding a scheduler or deployment
workflow.

Use `make local-kubernetes-evidence-bundle` against a running proof cluster when
you want pods, events, logs, endpoints, rollout status, Dapr logs, and admission state in
one local artifact. Use `make local-kubernetes-admission-report` before adding
`local-kubernetes` to a workload contract; it explains missing manifests,
config/secret injection, Dapr sidecar expectations, and probe/job expectations.

## Platform Toolkit Validation

Use this when validating the repo as a local-first delivery toolkit, not just
as a running API:

```bash
make platform-toolkit-validate-local
```

Use this shorter target when the local stack is already warm and you want a
fast confidence pass:

```bash
make platform-toolkit-smoke-local
```

It runs the standard local startup path, verifies `/health`, `/ready`, and
`/metrics`, publishes a CloudEvent through the local Dapr sidecar and confirms
the event consumer recorded it, runs the data export job, emits an operational
snapshot, runs configured integration checks, runs the `open_dataset_pipeline`
workload, and finishes with
`make runtime-conformance`.

The target prints section headers before each slice. Docker and pytest still
show their native output so failures stay close to the tool that produced them.
The API check uses `make api-smoke`, which retries briefly while the container
finishes startup.

Startup targets pass Compose's orphan cleanup flag so stale containers from an
older project shape do not obscure the current run. Use `make local-reset` only
when you also want to remove local volumes.

## Local Data Artifacts

The data export and open dataset workloads write to the `data_exports` Docker
volume. Use these helpers to inspect or reset the local artifact surface:

```bash
make data-export
make operational-snapshot
INTEGRATION_CHECK_TARGETS=api=http://api:8000/health make integration-check
make open-dataset-pipeline
make data-artifacts-list
make data-artifacts-shell
make data-artifacts-clean
```

The local-first workload tracks also use the same artifact volume:

- `lake_orders_ingest_job` writes raw/curated Parquet and a manifest.
- `churn_model_train_job` writes a model artifact and manifest.
- `support_triage_llm` writes triage run evidence, evaluation evidence, and
  failed-run operator payloads.

Run the LLM host locally with:

```bash
docker compose --profile llm up support-triage-llm
curl --fail --show-error http://127.0.0.1:8083/ready
curl --fail --show-error \
  -H "Content-Type: application/json" \
  --data '{"ticket_id":"T-local","subject":"Production API is down","body":"Checkout is unavailable","customer_tier":"enterprise","run_id":"local-triage"}' \
  http://127.0.0.1:8083/triage
curl --fail --show-error \
  -H "Content-Type: application/json" \
  --data '{"run_id":"local-eval"}' \
  http://127.0.0.1:8083/evaluate
```

## Migration Rollout Walkthrough

1. Start Postgres and PgBouncer.
2. Apply Liquibase migrations.
3. Seed local data.
4. Start the API.
5. Advance `WRITE_MODE` to `dual`.
6. Run the backfill worker.
7. Advance `READ_MODE` to `new`.
8. Run tests.
9. Advance `WRITE_MODE` to `new`.
10. Apply the contract migration when ready.

Commands:

```bash
curl --fail --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"mode":"dual"}' \
  http://127.0.0.1:8000/admin/write-mode

make backfill-once

curl --fail --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"mode":"new"}' \
  http://127.0.0.1:8000/admin/read-mode
```

## Quality Checks

```bash
uv sync --all-packages --group dev --group scripts --group test
make lint
uv run pytest tests/ -v
```

Tests read migration phase from `app_runtime_config` and skip phase-specific
assertions when needed.

## Optional Targets

```bash
make observability
make dapr-up
make data-export
make operational-snapshot
INTEGRATION_CHECK_TARGETS=api=http://api:8000/health make integration-check
make open-dataset-pipeline
```

## Common Targets

```bash
make help
make dev
make local-up
make local-down
make local-reset
make observability
make dapr-up
make migrate
make seed
make api-smoke
make backfill-once
make data-export
make operational-snapshot
INTEGRATION_CHECK_TARGETS=api=http://api:8000/health make integration-check
make data-artifacts-list
make open-dataset-pipeline
docker compose --profile llm up support-triage-llm
make test
make lint
make fmt
```

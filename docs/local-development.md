# Local Development

Canonical local setup and day-to-day runbook.

Use [Architecture](architecture.md) for ownership rules,
[Platform Contract](platform-contract.md) for portable workload rules, and the
[Proof Ladder](proof-ladder.md) when choosing how much proof a change needs.
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

## Command Map

| I want to... | Run |
|---|---|
| find the right command group | `make help-local`, `make help-proof`, `make help-cloud` |
| check a cold workstation | `make platform-doctor`, `make workload-readiness` |
| inspect local proof maturity | `make workload-readiness-local`, `make local-kubernetes-admission-report` |
| prove contracts fast | `make workload-readiness`, `make runtime-conformance`, `make local-kubernetes-contracts` |
| run the default local app host path | `make dev`, `make migrate`, `make seed`, `make local-app-up` |
| run the API with local observability | `make local-up` |
| prove the local delivery toolkit | `make platform-toolkit-validate-local` |
| prove rollout/rollback locally | `make local-kubernetes-rollout-proof` |
| capture local Kubernetes runtime evidence | `make local-kubernetes-evidence-drill` |
| validate cloud readiness without applying infra | `make platform-toolkit-validate-cloud` |

`local-kubernetes-admission-report` is static and safe to run first.
`not-ready` is expected for workloads that are intentionally local Compose only.

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
make platform-doctor
make workload-readiness
```

Use the local Kubernetes bootstrap only when you are proving that runtime target:

```bash
make local-kubernetes-contracts
make local-kubernetes-admission-report
make local-kubernetes-evidence-drill
make lint-policy
make lint-docs
```

`local-kubernetes-contracts` is the fast static check used by CI.
`local-kubernetes-admission-report` explains readiness before a live run.
`local-kubernetes-evidence-drill` is the live proof. Success means Docker
daemon access works, kind can create a local cluster, static Kubernetes
manifests satisfy the workload contract, selected jobs complete, Dapr eventing
works, and evidence is captured. If a command fails before reaching Kubernetes,
fix the toolchain first; if it fails inside the cluster, inspect the workload
evidence.

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
make workload-readiness
make dev
make migrate
make seed
make local-app-up
curl --fail --show-error http://127.0.0.1:8000/health
```

Use stepwise Docker commands only when you intentionally want the API without
the full local profile.

`make platform-doctor` checks local tools, Docker daemon access, expected repo
files, workload readiness, and default local Compose port availability. If a
port is already owned by this repo's running Compose service, the doctor treats
it as ready; otherwise it tells you which `*_PORT` override to set. For the API
port, set `APP_PORT` and the matching `LOCAL_API_BASE_URL` used by `api-smoke`.
Ports needed by the fast app-host proof are blockers; observability-only ports
are warnings until you choose `make local-up`. GitHub auth and cloud-only tools
are warnings in the local doctor; `make platform-doctor-cloud` promotes the
cloud operator checks. The doctor is a human diagnostic, not a CI gate.

## Local Kubernetes Proof

Use local Kubernetes when Compose is too small to prove network, storage,
compute, probes, jobs, service identity, or config/secret injection. The active
local Kubernetes target uses `kind` and static manifests only. The proof ladder
explains when this rung is warranted; `infra/local-kubernetes/README.md` owns
manifest boundaries and maintenance rules.

```bash
make local-kubernetes-contracts
make local-kubernetes-admission-report
make local-kubernetes-rollout-proof
make local-kubernetes-evidence-drill
```

This proves selected workloads against Postgres, PgBouncer, Liquibase, Redis,
Dapr sidecar wiring, Services, probes, Secrets, ConfigMaps, Jobs, and
PersistentVolumeClaims. It is not cloud Kubernetes, Helm, CRDs, or a platform
control plane.

Use `make local-kubernetes-rollout-proof` for local API Deployment
rollout/rollback evidence. Use `make local-kubernetes-evidence-drill` for the
repeatable runtime evidence capture; it includes the existing Dapr pub/sub
workload boundary and captures pods, events, logs, endpoints, rollout status,
Dapr logs, and admission state.

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

`platform-toolkit-smoke-local` runs the standard local startup path, verifies
`/health`, `/ready`, and `/metrics`, publishes a CloudEvent through the local
Dapr sidecar, and runs one bounded backfill batch. It intentionally starts only
the app-host services it needs; use `make local-up` or `make observability` when
you also need Prometheus, Loki, Tempo, Promtail, and Grafana.

`platform-toolkit-validate-local` is the full local Compose proof. It also runs
the data export job, emits an operational snapshot, runs configured integration
checks, runs the `open_dataset_pipeline` workload, and finishes with
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

## Current Target Inventory

Use the focused Make help views for the current command list:

```bash
make help-local
make help-proof
make help-cloud
make help-operator
```

Keep this page for workflow guidance; keep target inventory in the Makefile.

# Adding Workloads

Task guide for adding one workload under `apps/` with the smallest complete
platform footprint.

Canonical design truth lives in:

- [Platform Contract](platform-contract.md)
- [Architecture](architecture.md)
- [Platform Capabilities](platform-capabilities.md)

## Order

1. Declare workload intent in `platform/workloads.json`.
2. Choose one or more existing workload patterns from `platform/workload-patterns.json`.
3. Add the host under `apps/`.
4. Reuse `packages/` only for truly shared behavior.
5. Wire local and shared platform concerns.
6. Wire the current runtime-target realization.
7. Add tests and docs.

## Pick The Operational Class First

| Class | Use |
|---|---|
| `edge-service` | externally routed HTTP workload |
| `internal-service` | long-running internal service |
| `operator-job` | manually or CI-triggered task |
| `scheduled-job` | recurring scheduler-triggered task |

This choice drives `platform/workloads.json`, health/readiness/metrics,
Compose/workflow/runtime-target ownership, and alarm/evidence expectations.

Inspect current declared shapes:

```bash
make workload-capability-matrix
make workload-use-case-matrix
```

Preview or apply a starter workload bundle from the stable-center patterns:

```bash
make scaffold-workload ARGS='--name inventory_dashboard --pattern edge-service --use-case dashboard --service-port 8092'
make scaffold-workload ARGS='--name inventory_dashboard --pattern edge-service --use-case dashboard --service-port 8092 --apply'
```

Promote the scaffold to the current reviewed AWS runtime only when it is ready:

```bash
make scaffold-workload ARGS='--name inventory_dashboard --pattern edge-service --use-case dashboard --service-port 8092 --admitted-runtime aws-ecs --apply'
```

The scaffold command creates a thin host under `apps/`, a starter app test,
updates `platform/workloads.json`, updates `platform/runtime-conformance.json`,
adds a Backstage component, and inserts a local Compose service block. It
defaults to `local-compose` support so new workloads can start locally before
they are admitted to a cloud runtime. Treat it as the starting point, then keep
the host thin and finish any bespoke business behavior or runtime wiring
explicitly.

## Add The Host

Create:

- `apps/<name>/main.py`
- `apps/<name>/config.py`
- `apps/<name>/pyproject.toml`

Host rules:

- keep the host thin
- read settings
- wire adapters
- expose routes or a process entrypoint
- emit workload-level operational events

Put shared behavior in:

- `packages/domain`
- `packages/application`
- `packages/infrastructure`

Adapter rule:

- add business ports and use cases before adding provider-specific code
- add database, pub/sub, storage, or HTTP client adapters in `packages/infrastructure`
- keep runtime-target realization details in `infra/`, workflows, and scripts

## Update The Workload Contract

Add the workload to `platform/workloads.json` with:

- `name`
- `kind`
- `patterns`
- `use_cases`
- `app_path`
- `runtime.supported`
- `runtime.admitted`
- `operational`
- `image`
- `config`
- `database` only when the workload actually needs relational data
- `service` for HTTP workloads
- `job` for jobs
- `dapr` only when a real Dapr capability is needed
- `edge.auth_mode` and `verification` when the workload is the primary edge

Do not add:

- AWS resource names
- ECS service/task family details
- managed-Kubernetes manifest details
- queue URLs, topic ARNs, bucket ARNs
- Terraform wiring

`use_cases` rules:

- describe workload intent, not runtime implementation
- use lowercase kebab-case strings such as `http-api`, `dashboard`, `connector`, `event-consumer`, or `scheduled-pipeline`
- keep them useful for catalog search, templates, and future self-service entrypoints

## Choose The Smallest Existing Pattern

| Need | Pattern |
|---|---|
| public HTTP API | pattern `edge-service`, reference host `apps/api` |
| internal Dapr-backed service | pattern `internal-async-service`, reference host `apps/event_consumer` |
| operator-triggered job | pattern `operator-job`, reference host `apps/backfill_worker` |
| scheduled export job | patterns `scheduled-job` + `export-job`, reference host `apps/data_export_job` |

Reuse `platform/workload.Dockerfile` unless there is a concrete reason not to.
If a workload needs a different container shape, declare `image.dockerfile`
and `image.context` in `platform/workloads.json` instead of hardcoding build
logic elsewhere.

If you are exploring open-source data tooling such as file loaders, DuckDB, or
dbt-style transformations, keep teaching samples in `examples/`. If the code is
a real workload host with a contract, tests, local proof, and owner, keep it in
`apps/` and declare `runtime.supported: ["local-compose"]`. Add `aws-ecs` to
`runtime.admitted` only after reviewed infra realization and delivery ownership
exist.

## Wire Only Needed Concerns

- `platform/concerns/dapr/`
- `platform/concerns/observability/`
- `platform/runtime-conformance.json`
- `compose.yaml`
- `infra/app/workload_inventory.tf` for the current AWS target

Touch GitHub workflows, `infra/app`, and observability scripts only when the
workload changes build/deploy inventory, runtime resources, or platform-visible
signals.

Rule: extend metadata-driven paths before adding handwritten inventory.
Rule: prefer selecting runtime behavior from `patterns`, edge metadata, or workload capability metadata before adding new workload-name branches.
Rule: reserve new runtime-target seams in docs and ownership before inventing a
second workload specification.

Managed-Kubernetes note:

- managed Kubernetes is a future runtime target, not the platform control plane
- reserve reusable target modules under `infra/catalog/managed-kubernetes/`
- do not add ArgoCD, Helm/Kustomize packaging, or cluster-control-plane assumptions unless that target becomes a repeated runtime need

## Verify

```bash
uv run pytest tests/contracts -q
uv run pytest tests/apps -q
make runtime-conformance
```

Add narrower tests when possible:

- `tests/apps/`
- `tests/application/`
- `tests/infrastructure/`

## Done Checklist

- operational class is explicit in `platform/workloads.json`
- runtime support and admission are explicit in `platform/workloads.json`
- host stayed thin
- provider details stayed at the platform edge
- stable center stayed recognizable: no second workload-intent source was added
- existing Dapr, observability, and delivery patterns were reused
- smallest complete set of tests and docs was updated

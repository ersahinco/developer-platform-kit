# Adding Workloads

Task guide for adding one workload under `apps/` with the smallest complete
platform footprint.

Canonical design truth lives in:

- [Platform Contract](platform-contract.md)
- [Architecture](architecture.md)
- [Platform Capabilities](platform-capabilities.md)

## Order

1. Declare workload intent in `platform/workloads.json`.
2. Add the host under `apps/`.
3. Reuse `packages/` only for truly shared behavior.
4. Wire local and shared platform concerns.
5. Wire the current runtime-target realization.
6. Add tests and docs.

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
- `use_cases`
- `app_path`
- `operational`
- `image`
- `config`
- `database` only when the workload actually needs relational data
- `service` for HTTP workloads
- `job` for jobs
- `dapr` only when a real Dapr capability is needed

Do not add:

- AWS resource names
- ECS service/task family details
- managed-Kubernetes manifest details
- queue URLs, topic ARNs, bucket ARNs
- Terraform wiring

`use_cases` rules:

- describe workload intent, not runtime implementation
- use lowercase kebab-case strings such as `http-api`, `dashboard`, `connector`, `event-consumer`, `data-pipeline`
- keep them useful for catalog search, templates, and future self-service entrypoints

## Choose The Smallest Existing Pattern

| Need | Pattern |
|---|---|
| public HTTP API | `apps/api` |
| internal Dapr-backed service | `apps/order_event_consumer` |
| operator-triggered job | `apps/backfill_worker` |
| scheduled export job | `apps/data_export_job` |

Reuse `platform/workload.Dockerfile` unless there is a concrete reason not to.
If a workload needs a different container shape, declare `image.dockerfile`
and `image.context` in `platform/workloads.json` instead of hardcoding build
logic elsewhere.

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
- host stayed thin
- provider details stayed at the platform edge
- stable center stayed recognizable: no second workload-intent source was added
- existing Dapr, observability, and delivery patterns were reused
- smallest complete set of tests and docs was updated

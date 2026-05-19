# Adding Workloads

Use this guide when adding a new reference workload under `apps/`.

The goal is to add one workload with the smallest complete platform footprint,
not to introduce a new abstraction layer.

This is a task guide, not the source of truth for platform design.

Use companion docs when needed:

- [Platform Contract](platform-contract.md) for the portable workload contract
- [Architecture](architecture.md) for repo placement and ownership rules
- [Platform Capabilities](platform-capabilities.md) for the currently available
  runtime patterns

## Onboarding Order

Follow this order so workload intent stays canonical:

1. declare workload intent in `platform/workloads.json`
2. add the host under `apps/`
3. add reusable behavior in `packages/` only if it is truly shared
4. wire local and runtime concerns
5. wire AWS runtime inventory
6. add tests and docs

## Decide The Operational Class First

Pick the workload role before writing code:

- `edge-service`: externally routed HTTP workload
- `internal-service`: long-running internal service
- `operator-job`: manually or CI-triggered task
- `scheduled-job`: recurring scheduler-triggered task

This choice affects:

- `platform/workloads.json`
- health/readiness/metrics expectations
- runtime ownership in Compose, workflows, and Terraform
- alarm and evidence expectations

The contract meaning of each class lives in
[Platform Contract](platform-contract.md#operational-class).

## Add The Host

Create:

- `apps/<name>/main.py`
- `apps/<name>/config.py`
- `apps/<name>/pyproject.toml`

The host should stay thin:

- read settings
- wire adapters
- expose routes or a process entrypoint
- emit workload-level operational events

Move reusable behavior into:

- `packages/domain` for pure business concepts
- `packages/application` for use cases and workflow logic
- `packages/infrastructure` for SQL, Dapr, storage, and runtime adapters

## Update The Workload Contract

Add the workload to `platform/workloads.json` with:

- `name`
- `kind`
- `app_path`
- `operational`
- `image`
- `config`
- `database`
- `service` for HTTP workloads
- `job` for jobs
- `dapr` only when a real Dapr capability is needed

Keep this file focused on workload need and portable behavior. Do not add:

- AWS resource names
- ECS service/task family details
- queue URLs, topic ARNs, bucket ARNs
- Terraform wiring

## Choose The Runtime Pattern

Use the smallest existing pattern that fits:

- public HTTP API pattern: `apps/api`
- internal Dapr-backed service pattern: `apps/order_event_consumer`
- operator-triggered job pattern: `apps/backfill_worker`
- scheduled export job pattern: `apps/data_export_job`

Reuse the shared workload Dockerfile unless there is a concrete reason not to.

## Wire Platform Concerns

Only wire the concerns the workload actually needs:

- Dapr under `platform/concerns/dapr/`
- observability under `platform/concerns/observability/`
- runtime conformance fixtures in `platform/runtime-conformance.json`

Keep platform concerns declarative and environment-owned. Do not create a
custom host framework or bespoke workload DSL.

## Add Delivery And Runtime Coverage

Update the smallest set of delivery/runtime surfaces needed:

- `compose.yaml` for local runtime
- `infra/app/workload_inventory.tf` for AWS runtime values derived from the workload contract
- GitHub workflows only if the workload changes build/deploy inventory
- `infra/app` only when runtime resources must change
- observability scripts only when the workload changes platform-visible signals

Prefer extending metadata-driven paths over adding new handwritten inventories.

## Verify

At minimum, run the relevant checks:

```bash
uv run pytest tests/contracts -q
uv run pytest tests/apps -q
make runtime-conformance
```

Add narrower tests when possible:

- workload host tests under `tests/apps/`
- application/use-case tests under `tests/application/`
- infrastructure adapter tests under `tests/infrastructure/`

## Review Questions

Before considering the workload complete, answer these:

- Is the operational class explicit in the workload spec?
- Did the host stay thin?
- Did provider details remain at the platform edge?
- Did I reuse existing Dapr, observability, and delivery patterns?
- Did I avoid adding a second source of workload truth?
- Did I update the smallest complete set of tests and docs?

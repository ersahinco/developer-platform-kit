# Adding Workloads

Task guide for adding one workload under `apps/` with the smallest complete
platform footprint.

Canonical design truth lives in:

- [Platform Contract](platform-contract.md)
- [Architecture](architecture.md)
- [Platform Capabilities](platform-capabilities.md)
- [Workload Observability](workload-observability.md)

## Order

1. Declare workload intent in `platform/workloads.json`.
2. Add the host under `apps/`.
3. Reuse `packages/` only for truly shared behavior.
4. Wire local and shared platform concerns.
5. Wire the current runtime-target realization.
6. Add tests and docs.

## Minimum Boundary Inputs

The first question is not whether the app is small or large. The useful
question is whether the workload boundary is explicit enough for a developer to
prove locally and for a runtime target to admit later.

Declare the smallest truthful set:

- image package and start command
- service port plus `/health`, `/ready`, and `/metrics` for HTTP workloads
- job trigger and idempotency expectation for job workloads
- config and secret names, never values
- network exposure and required private connectivity
- storage, database, and messaging needs only when the workload actually uses them
- authn/authz expectation, either app-local or runtime-owned
- logs, metrics, traces, and evidence the operator must inspect
- workload owner, supported runtime targets, and admitted runtime targets

A tiny container app can start as a real `apps/` workload with
`runtime.supported: ["local-compose"]`, no database, no Dapr, no cloud
admission, and no extra platform machinery. Add runtime admission only after
local proof, owner, evidence, and runtime realization exist.

## Tiny App Onboarding

Use this path for the smallest useful app host:

1. Add `apps/<name>/main.py`, `config.py`, and `pyproject.toml`.
2. Add one workload row in `platform/workloads.json` with owner, image package,
   command, config names, secret names, and `runtime.supported:
   ["local-compose"]`.
3. For an HTTP workload, expose `/health`, `/ready`, and `/metrics`; for a job,
   emit one structured terminal success or failure event.
4. Run local proof:

```bash
make workload-readiness-local
make workload-readiness-check
make platform-toolkit-smoke-local
```

5. Inspect evidence: service metrics, structured logs, job event payloads, data
   artifacts, and readiness output.
6. Add `local-kubernetes` support only when the workload needs richer local
   proof for Services, probes, jobs, storage, service identity, rollout/rollback,
   Dapr sidecar wiring, or config/secret injection. Use
   `make local-kubernetes-admission-report` before running a live drill.
7. Ask for `aws-ecs` admission only after the runtime owner adds the reviewed
   infra and delivery path.

Rule: copy a small existing workload shape, not a framework. The contract is
the onboarding surface; Compose and local Kubernetes are proof runtimes.
Candidate helpers, examples, and catalog entries may describe or check workload
boundaries, but they must not generate app code, redefine workload identity, or
own deployment choreography.

## Pick The Operational Class First

| Class | Use |
|---|---|
| `edge-service` | externally routed HTTP workload |
| `internal-service` | long-running internal service |
| `operator-job` | manually or CI-triggered task |
| `scheduled-job` | recurring scheduler-triggered task |

This choice anchors the workload contract, health/readiness/metrics
expectations, and the current platform-edge wiring for Compose, workflows, and
runtime realization.

Inspect current declared classes and labels:

```bash
make workload-capability-matrix
make workload-readiness
make workload-readiness-check
uv run python scripts/platform/workload_readiness.py --view addition
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
- follow the service metric or job terminal event shape in
  [Workload Observability](workload-observability.md)

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
- `owner`
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

## Copy The Smallest Existing Reference

Use existing workloads as examples, not a generator. Copy only the pieces that
match the new workload and finish the contract directly.

| Need | Reference |
|---|---|
| public HTTP API | operational class `edge-service`, host `apps/api` |
| internal Dapr-backed service | operational class `internal-service`, host `apps/event_consumer` |
| operator-triggered job | operational class `operator-job`, host `apps/backfill_worker` |
| scheduled export job | operational class `scheduled-job`, host `apps/data_export_job` |

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

## Promote Local To AWS

Use this order when promoting a local-first workload to `aws-ecs`:

1. Keep `runtime.supported` on `local-compose` while the workload is still proving its contract locally.
2. Declare a portable `owner` in `platform/workloads.json`.
3. Add the AWS runtime realization in `infra/app/` and only the needed catalog/runtime wiring.
4. Confirm the workload is picked up by build, catalog, contract, and runtime-conformance checks.
5. Add `aws-ecs` to `runtime.admitted` only after the reviewed delivery path and runtime owner exist.

Rule: local proof comes first, cloud admission comes second.

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
Rule: prefer selecting runtime behavior from explicit workload contract fields, edge metadata, or workload capability metadata before adding new workload-name branches.
Rule: reserve new runtime-target seams in docs and ownership before inventing a
second workload specification.

Managed provider-edge note:

- keep workload identity in `platform/workloads.json`; do not turn provider-edge wiring into a second workload contract
- do not add a new runtime-target catalog branch until a repeated workload need and clear runtime ownership exist
- keep provider-edge options as documented horizon guidance until they become reviewed runtime work

## Verify

```bash
make workload-readiness
make workload-readiness-check
uv run python scripts/platform/workload_readiness.py --view addition
uv run pytest tests/contracts -q
uv run pytest tests/apps -q
make runtime-conformance
```

Add narrower tests when possible:

- `tests/apps/`
- `tests/application/`
- `tests/infrastructure/`

## Paved Road Commands

Run these before asking for AWS admission, then use
[Operator Day 2 Commands](operator-day-2.md) for the full operator path from
doctor checks through evidence download:

```bash
make workload-readiness
make workload-readiness-check
make lint-app
make lint-workflows
make lint-policy
make runtime-conformance
make workflow-dry-run-validate-gh
```

For local proof:

```bash
make workload-readiness-local
make local-kubernetes-admission-report
make platform-toolkit-smoke-local
make platform-toolkit-validate-local
```

`platform-toolkit-smoke-local` starts only the app-host services, Dapr path, and
one bounded backfill batch. Use `platform-toolkit-validate-local` when you need
the full local Compose proof ladder with observability and data jobs.

For safe cloud readiness:

```bash
make platform-toolkit-validate-cloud
```

Use the report first, then the check. If `make workload-readiness-check` says a
workload lacks a run workflow, evidence surface, terminal job event, log group,
logs contract, secret injection proof, or config contract, fix that paved-road
gap before adding more workload behavior.

## Done Checklist

- operational class is explicit in `platform/workloads.json`
- workload owner is explicit in `platform/workloads.json`
- runtime support and admission are explicit in `platform/workloads.json`
- host stayed thin
- provider details stayed at the platform edge
- stable center stayed recognizable: no second workload-intent source was added
- existing Dapr, observability, and delivery concerns were reused
- smallest complete set of tests and docs was updated

# aws-sdlc-containers

Developer-first delivery toolkit for portable workload boundaries, local proof,
AWS ECS realization, and evidence-driven operations.

Short form: standardize the delivery workflow, do not replace the tools.

The stable center of the repo is the workload contract and the platform
catalog. Together they make the monorepo a practical toolkit for teams to
standardize app development, infrastructure ownership, build, test, delivery,
and evidence without hiding standard tools behind private machinery. Runtime
targets are pluggable implementations at the platform edge. Local Compose is
the fastest feedback runtime; local Kubernetes is the richer local proof
runtime; AWS/ECS is the current reviewed production realization. Enterprise
runtime choices stay candidate-only until a real organizational requirement has
an owner, conformance path, evidence artifact, failure mode, and runbook.
The repo also ships a conventional Backstage descriptor in `catalog-info.yaml`
so a portal or software catalog can ingest the monorepo without custom glue.

App size is not the fit test. A tiny container, a long-running app host, a
scheduled job, or a larger data/ML workload fits when its ports,
health/readiness, config, secrets, network, storage, auth, logs/metrics,
ownership, and evidence needs are explicit.

## Who This Is For

Use this repo when you want:

- a repeatable path for app hosts, jobs, data workloads, ML workloads, and LLM
  workloads
- local proof before cloud changes
- local Kubernetes proof when Compose is too small for network, storage, probes,
  jobs, or service identity
- explicit workload boundaries before platform ceremony
- opinionated build, test, delivery, infra, evidence, and app-host conventions
- AWS ECS delivery with explicit review, evidence, and operator handoff
- runtime standardization without putting Okta, Kong, OPA, Datadog, or Splunk
  into workload metadata

Do not use it as:

- a generic provider-neutral infrastructure toolkit
- a self-service portal or control plane before the workload boundary is clear
- a runtime platform replacement for ECS, Lambda, Kubernetes, Cloud Run, VMs, or
  on-prem hosts
- a YAML DSL for every deployment concern
- a place to hide platform magic behind generated per-app behavior
- a place for each app team to pick random delivery, auth, observability, or
  policy tools when shared runtime capabilities should own those choices
- a place to install enterprise tools before a real workload and runtime owner need them

## What This Repo Standardizes

- Platform center: workload contract plus reusable catalog and concern definitions
- Workload contract: `platform/workloads.json`; local/CI proof in `platform/runtime-conformance.json`
- Boundaries: thin `apps/*` hosts, reusable `packages/*`, pluggable runtime targets realized at the edge in `infra/*`, workflows, and Compose
- Ownership: each workload declares a portable owner before cloud runtime admission
- DevEx: repeatable app-host conventions, local proof, checks, and evidence before runtime-specific work
- Delivery: build before deploy, plan before apply, immutable image tags, release evidence
- Operations: observability baseline, runbooks, contract and architecture tests

## Repo Map

| Path | Owns |
|---|---|
| `apps/` | Contract-governed workload hosts, including local-only workloads |
| `examples/` | Teaching, demo, and reference-only samples |
| `packages/` | Domain, application, infrastructure packages |
| `db/` | Liquibase changelog and Postgres assets |
| `infra/` | Runtime-target Terraform roots plus reusable catalog parts; current production target is AWS |
| `platform/` | Workload contract, shared image, and shared runtime concerns |
| `scripts/` | CI, release, operator, observability, data helpers |
| `tests/` | API, contract, runtime, infrastructure checks |
| `docs/` | Canonical operator and design docs |
| `catalog-info.yaml` | Optional Backstage catalog entities for self-service discovery |

## Start Here

| Need | Read |
|---|---|
| Canonical doc map | [docs/README.md](docs/README.md) |
| First local-to-cloud validation pass | [docs/first-30-minutes.md](docs/first-30-minutes.md) |
| Repo boundaries | [docs/architecture.md](docs/architecture.md) |
| Portable workload expectations | [docs/platform-contract.md](docs/platform-contract.md) |
| Runtime hosts and reusable packages | [apps/README.md](apps/README.md), [packages/README.md](packages/README.md) |
| Local workflow | [docs/local-development.md](docs/local-development.md) |
| AWS delivery and operator flow | [docs/operator-day-2.md](docs/operator-day-2.md), [docs/deployment.md](docs/deployment.md) |
| Incident response | [docs/runbooks/README.md](docs/runbooks/README.md) |
| Current work state | [docs/roadmaps.md](docs/roadmaps.md) |

## Quick Local Path

For a first pass, use the opinionated validation path instead of sampling every
target in the Makefile:

```bash
make platform-doctor
make platform-toolkit-validate-local
make capability-proof-local-live
```

Use this shorter path for daily work after the stack is already familiar:

```bash
make lint
make platform-toolkit-smoke-local
make runtime-conformance
```

Use this non-mutating cloud readiness path before opening cloud-changing work:

```bash
make platform-doctor-cloud
make platform-toolkit-validate-cloud
```

The doctor targets are human diagnostics. They check expected tools, Docker,
GitHub auth, optional cloud tools, repo files, and workload readiness with short
command hints. `capability-proof-local-live` is an isolated live local drill for
runtime capability behavior; it is not the full local validation journey.

For full local setup, exact inventory views, and optional observability helpers,
use [docs/local-development.md](docs/local-development.md) and
[docs/first-30-minutes.md](docs/first-30-minutes.md).

## Use It In Anger

1. Prove the local path:
   `make platform-toolkit-validate-local`
2. Prove the live local runtime blades:
   `make capability-proof-local-live`
3. Add or onboard one real workload:
   [docs/adding-workloads.md](docs/adding-workloads.md)
4. Inspect evidence and readiness:
   `make workload-readiness`, `make capability-proof-local`, `make data-artifacts-list`
5. Decide runtime admission:
   use [docs/runtime-toolkit.md](docs/runtime-toolkit.md),
   `make capability-proof-cloud`, and `make enterprise-runtime-fit-check`

## Keep It Useful

The repo already has enough capability to absorb real workloads. Prefer use and
small corrections over new machinery:

- add scripts only when they answer an operator question directly
- keep `platform/workloads.json` as workload identity, not deployment choreography
- keep live capability proof narrow; full local validation belongs to
  `make platform-toolkit-validate-local`
- keep enterprise integrations candidate-only until a runtime owner, evidence,
  conformance, failure mode, and runbook exist

Useful inventory commands when you need them:

```bash
make workload-capability-matrix
make workload-use-case-matrix
make workload-readiness
```

## Delivery Shape

| Workflow | Owns |
|---|---|
| `app-build.yml` | Validate, test, runtime conformance, build, scan, push |
| `app-deploy.yml` | Deploy app images, verify runtime, emit release evidence |
| `data-*.yml` | Apply schema phases, switch runtime modes, promote support jobs, run backfills |
| `infra-plan.yml` | Reviewed Terraform plan only |
| `infra-apply.yml` | Apply reviewed Terraform plan only |

Cloud-changing jobs stay split so review happens between build and deploy, and
between plan and apply.

## Operator Path

Shared review commands and rollout checks live in
[docs/deployment.md](docs/deployment.md#review-checklist).
Incident selection lives in
[docs/runbooks/README.md](docs/runbooks/README.md).

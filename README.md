# aws-sdlc-containers

This delivery toolkit helps teams define portable workload boundaries, prove
them locally, deliver them through GitHub Actions, and realize them at the
platform edge with runtime evidence, without hiding standard DevOps tools behind
a framework.

Short form: standardize the delivery workflow, do not replace the tools.

The stable center of the repo is the workload contract and the platform
catalog. Together they make the monorepo a practical toolkit for teams to
standardize app development, infrastructure ownership, build, test, delivery,
and evidence without hiding standard tools behind private machinery. Runtime
targets are pluggable implementations at the platform edge. Local Compose is
the fastest feedback runtime; local Kubernetes is the richer local proof
runtime; AWS/ECS is the current reviewed production realization. Enterprise
runtime choices can incubate as bounded candidates before demand reaches scale;
they stay out of active defaults until a concrete proof, owner, conformance
path, evidence artifact, failure mode, and runbook exist.
The repo also ships a conventional Backstage descriptor in `catalog-info.yaml`
so a portal or software catalog can ingest the monorepo without custom glue.

The monorepo is capability-rich but deliberately lean. It includes modern
GitHub Actions lanes for infra, app, and data delivery; infrastructure
capabilities from network placement through database, object storage, messaging,
jobs, and scheduler realization; and an app development contract that brings
portable concerns such as Dapr, observability, config, secrets, and evidence
into the app host from the start.

Dapr is the core distributed-application boundary: app teams use stable APIs
for building blocks while platform engineering owns component implementations,
scoping, resiliency, security, telemetry, and runtime delivery. Pub/sub is
production-proven; local service invocation is exercised by the booking
consistency workload; further building blocks grow through owned experiments.

App size is not the fit test. A tiny container, a long-running app host, or a
scheduled job fits when its ports,
health/readiness, config, secrets, network, storage, auth, logs/metrics,
ownership, and evidence needs are explicit.

## Who This Is For

Use this repo when you want:

- a repeatable path for app hosts and jobs
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
- a place to install enterprise tools without a bounded capability outcome, concrete proof, and owner

## What This Repo Standardizes

- Platform center: workload contract plus reusable catalog and concern definitions
- Workload contract: `platform/workloads.json`; local/CI proof in `platform/runtime-conformance.json`
- Boundaries: thin `apps/*` hosts, reusable `packages/*`, pluggable runtime targets realized at the edge in `infra/*`, workflows, and Compose
- Capabilities: network, database, object storage, messaging, jobs, scheduling, Dapr, observability, secrets, and evidence selected by workload need or an owned pre-scale proof
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
| Which proof command to run | `make help-proof`, [docs/proof-ladder.md](docs/proof-ladder.md), [docs/local-development.md](docs/local-development.md#command-map) |
| First local-to-cloud validation pass | [docs/first-30-minutes.md](docs/first-30-minutes.md) |
| Repo boundaries | [docs/architecture.md](docs/architecture.md) |
| Portable workload expectations | [docs/platform-contract.md](docs/platform-contract.md) |
| Runtime hosts and reusable packages | [apps/README.md](apps/README.md), [packages/README.md](packages/README.md) |
| Local workflow | [docs/local-development.md](docs/local-development.md) |
| DevOps gates and reusable pipeline shape | [docs/devops-toolchain.md](docs/devops-toolchain.md), [docs/deployment.md](docs/deployment.md) |
| AWS delivery and operator flow | [docs/operator-day-2.md](docs/operator-day-2.md), [docs/deployment.md](docs/deployment.md) |
| Greenfield and brownfield deployment options | [docs/deployment-options.md](docs/deployment-options.md) |
| Incident response | [docs/runbooks/README.md](docs/runbooks/README.md) |
| Current work state | [docs/roadmaps.md](docs/roadmaps.md) |

## Quick Local Path

Start with the smallest proof that answers the question in front of you. Use
the grouped help views instead of sampling every target in the Makefile:

```bash
make help-local
make help-proof
```

For a cold workstation check, stay local and non-mutating:

```bash
make platform-doctor
make workload-readiness
make local-kubernetes-admission-report
```

For cheap static proof before starting the app host:

```bash
make workload-readiness-check
make local-kubernetes-contracts
```

For the first live local app-host proof:

```bash
make platform-toolkit-smoke-local
```

This smoke path avoids the local observability stack; use `make local-up` when
you need Prometheus, Loki, Tempo, Promtail, and Grafana.

For the full local Compose proof ladder:

```bash
make platform-toolkit-validate-local
```

When the risk is the local runtime boundary itself, use the isolated Compose
drill for token auth, health, readiness, metrics, structured logs, and local
observability:

```bash
make local-compose-live-proof
```

For the richer local Kubernetes proof runtime target, first inspect admission
and then run the live drill only when the workload needs that level of proof:

```bash
make workload-readiness-local
make local-kubernetes-admission-report
make local-kubernetes-evidence-drill
```

Use this non-mutating cloud readiness path before opening cloud-changing work:

```bash
make workload-readiness-cloud
make platform-doctor-cloud
make platform-toolkit-validate-cloud
```

`workload-readiness-cloud` shows the AWS admission, policy/delivery gate,
structured log contract, secret injection proof, delivery workflow, evidence
artifact, log group, and rollback proof category for each workload.

The doctor targets are human diagnostics. The local doctor requires local tools,
Docker, repo files, and workload readiness; cloud-only tools and GitHub auth are
warnings unless you run `make platform-doctor-cloud`.

For full local setup, exact inventory views, and optional observability helpers,
use [docs/local-development.md](docs/local-development.md) and
[docs/first-30-minutes.md](docs/first-30-minutes.md).

## Use It In Anger

1. Inspect workload and runtime maturity:
   `make workload-readiness`
2. Prove the local Compose path:
   `make platform-toolkit-validate-local`
3. Use local Kubernetes proof when Compose is too small:
   `make workload-readiness-local`, `make local-kubernetes-evidence-drill`
4. Add or onboard one real workload:
   [docs/adding-workloads.md](docs/adding-workloads.md)
5. Inspect evidence and artifacts:
   `make workload-readiness`, `make data-artifacts-list`
6. Decide runtime admission:
   use [docs/runtime-toolkit.md](docs/runtime-toolkit.md),
   `make workload-readiness-cloud`, and `make runtime-defaults`

## Keep It Useful

The repo already has enough capability to absorb real workloads. Prefer use and
small corrections, and extend it through bounded proofs rather than new
machinery:

- add scripts only when they answer an operator question directly
- keep `platform/workloads.json` as workload identity, not deployment choreography
- keep live capability proof narrow; full local validation belongs to
  `make platform-toolkit-validate-local`
- let enterprise integrations incubate as contract-backed candidates, but keep
  them out of active defaults until a runtime owner, evidence, conformance,
  failure mode, and runbook exist

Useful inventory commands when you need them:

```bash
make monorepo-capability-profile
make monorepo-capability-profile-md
make monorepo-capability-profile-check
make workload-capability-matrix
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

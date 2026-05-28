# aws-sdlc-containers

Opinionated platform monorepo and delivery toolkit.

Short form: standardize the delivery workflow, do not replace the tools.

The stable center of the repo is the workload contract and the platform
catalog. Together they make the monorepo a practical toolkit for engineers to
build standardized applications without replacing the tools they already use.
Runtime targets are pluggable implementations at the platform edge. Local
Compose is the fast feedback runtime; AWS/ECS is the current reviewed
production runtime. Future provider-edge integrations stay a horizon topic
until a real workload needs them and the runtime ownership is clear.
The repo also ships a conventional Backstage descriptor in `catalog-info.yaml`
so a portal or software catalog can ingest the monorepo without custom glue.

## What This Repo Standardizes

- Platform center: workload contract plus reusable catalog and concern definitions
- Workload contract: `platform/workloads.json`; local/CI proof in `platform/runtime-conformance.json`
- Boundaries: thin `apps/*` hosts, reusable `packages/*`, pluggable runtime targets realized at the edge in `infra/*`, workflows, and Compose
- Ownership: each workload declares a portable owner before cloud runtime admission
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
| Repo boundaries | [docs/architecture.md](docs/architecture.md) |
| Portable workload expectations | [docs/platform-contract.md](docs/platform-contract.md) |
| Runtime hosts and reusable packages | [apps/README.md](apps/README.md), [packages/README.md](packages/README.md) |
| Local workflow | [docs/local-development.md](docs/local-development.md) |
| AWS delivery and operator flow | [docs/deployment.md](docs/deployment.md) |
| Incident response | [docs/runbooks/README.md](docs/runbooks/README.md) |
| Current work state | [docs/roadmaps.md](docs/roadmaps.md) |

## Quick Local Path

```bash
make dev
make migrate
make seed
make local-up
curl --fail --show-error http://localhost:8000/health
```

Common checks:

```bash
uv sync --all-packages --group dev --group scripts --group test
make lint
uv run pytest tests/ -v
```

Useful inventory views:

```bash
make workload-capability-matrix
make workload-use-case-matrix
make platform-inventory-json
```

Optional local extras:

```bash
make observability
make dapr-up
```

For full local setup, use [docs/local-development.md](docs/local-development.md).

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

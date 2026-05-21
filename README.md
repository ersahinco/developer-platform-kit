# aws-sdlc-containers

Opinionated cloud-native delivery toolkit monorepo.

Short form: standardize the delivery workflow, do not replace the tools.

The stable center of the repo is the workload contract and the platform
catalog. Runtime targets are pluggable implementations at the platform edge.
The current primary runtime target is AWS/ECS. Portable value lives in the
workload contract, package boundaries, container builds, config and secrets,
observability, CI gates, rollout safety, and operator evidence.
The repo also ships a conventional Backstage descriptor in `catalog-info.yaml`
so a portal or software catalog can ingest the monorepo without custom glue.

## What This Repo Standardizes

- Platform center: workload contract plus reusable catalog and concern definitions
- Workload contract: `platform/workloads.json`, `platform/runtime-conformance.json`
- Boundaries: thin `apps/*` hosts, reusable `packages/*`, pluggable runtime targets realized in `infra/*`
- Delivery: build before deploy, plan before apply, immutable image tags, release evidence
- Operations: observability baseline, runbooks, contract and architecture tests

## Repo Map

| Path | Owns |
|---|---|
| `apps/` | Reference workload hosts |
| `packages/` | Domain, application, infrastructure packages |
| `db/` | Liquibase changelog and Postgres assets |
| `infra/` | Runtime-target Terraform roots plus reusable catalog parts; current primary target is AWS |
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
| `app-deploy.yml` | Migrate, deploy, verify, register support workloads, emit release evidence |
| `infra-plan.yml` | Reviewed Terraform plan only |
| `infra-apply.yml` | Apply reviewed Terraform plan only |

Cloud-changing jobs stay split so review happens between build and deploy, and
between plan and apply.

## Operator Path

Shared review commands and rollout checks live in
[docs/deployment.md](docs/deployment.md#review-checklist).
Incident selection lives in
[docs/runbooks/README.md](docs/runbooks/README.md).

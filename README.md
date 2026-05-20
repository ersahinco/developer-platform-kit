# aws-sdlc-containers

Opinionated cloud-native delivery toolkit monorepo.

Short form: standardize the delivery workflow, do not replace the tools.

The current runtime target is AWS/ECS. The portable value lives in the
workload contract, package boundaries, container builds, config and secrets,
observability, CI gates, rollout safety, and operator evidence.

## What This Repo Standardizes

- Workload contract: `platform/workloads.json`, `platform/runtime-conformance.json`
- Boundaries: thin `apps/*` hosts, reusable `packages/*`, AWS runtime edge in `infra/*`
- Delivery: build before deploy, plan before apply, immutable image tags, release evidence
- Operations: observability baseline, runbooks, contract and architecture tests

## Repo Map

| Path | Owns |
|---|---|
| `apps/` | Reference workload hosts |
| `packages/` | Domain, application, infrastructure packages |
| `db/` | Liquibase changelog and Postgres assets |
| `infra/` | AWS platform and app Terraform roots plus reusable catalog parts |
| `platform/` | Workload metadata, shared image, shared runtime concerns |
| `scripts/` | CI, release, operator, observability, data helpers |
| `tests/` | API, contract, runtime, infrastructure checks |
| `docs/` | Canonical operator and design docs |

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

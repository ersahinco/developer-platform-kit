# DevOps Toolchain

This project should demonstrate a complete but lean DevOps toolchain around ECS.

## Current Toolchain

| Concern | Current mechanism |
|---|---|
| Source control | Git monorepo |
| Local orchestration | Docker Compose |
| Python dependency management | `uv` workspace |
| Local commit checks | pre-commit hooks |
| Tests | pytest |
| Python lint/format | ruff |
| Database migrations | Liquibase |
| Infrastructure as code | Terraform |
| Infrastructure checks | terraform fmt, terraform validate, tflint, checkov |
| CI/CD | GitHub Actions |
| AWS authentication | GitHub OIDC role assumption |
| Image registry | ECR |
| Image security | Trivy before push, ECR scanning configured in Terraform |
| Runtime | ECS Fargate |

## Hardening Goals

- Keep `.pre-commit-config.yaml` aligned with `make lint` and `make fmt`.
- Keep all quality gates runnable locally and in CI.
- Keep deployment confirmation manual for AWS-changing workflows.
- Document Bitbucket Pipelines equivalents without maintaining duplicate pipelines.
- Keep scripts small, explicit, and easy to inspect.

## Local Quality Commands

```bash
make pre-commit
make lint
make fmt
uv run pytest tests/ -v
```

`ruff` is declared in the root development dependency group so `uv run ruff`
does not depend on a globally installed binary.

## Naming Conventions

Keep names boring and ownership-oriented:

| Area | Convention |
|---|---|
| Apps | `apps/<runtime-entrypoint>/`, for example `api`, `backfill-worker`, `data-export-job`. |
| Packages | `packages/<library>/` with import names under `aws_sdlc_*`. |
| Terraform files | `base_*` for required stack concerns, `optional_*` for explicit extensions, `oidc_*` for GitHub role/policy concerns, and `support_*` for one-off operational tasks. |
| CI scripts | `scripts/ci_*` for GitHub Actions/AWS deployment helpers. |
| Local/operator scripts | Verb-first or domain-first names such as `run_liquibase.sh`, `db_tunnel.sh`, `seed_data.py`, and `smoke_test.py`. |

Do not add empty top-level folders from the inspired architecture. Create
`ops/`, `security/`, or extra `packages/*` only when there is real content and
a clear owner.

## Bitbucket Pipelines Equivalence

For interview and documentation purposes, the GitHub Actions workflow maps to
Bitbucket Pipelines as follows:

- `pull_request` workflows map to pull request pipelines.
- `workflow_dispatch` maps to manually triggered custom pipelines.
- GitHub Environments map to deployment environments.
- GitHub OIDC role assumption maps to Bitbucket OIDC federation with AWS STS.
- Reusable workflow steps map to YAML anchors or shared pipe definitions.

Do not add Bitbucket configuration unless this repo needs to run in Bitbucket.

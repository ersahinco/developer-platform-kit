# DevOps Toolchain

This project should demonstrate a complete but lean DevOps toolchain around ECS.

## Current Toolchain

| Concern | Current mechanism |
|---|---|
| Source control | Git monorepo |
| Local orchestration | Docker Compose |
| Python dependency management | `uv` workspace |
| Python dependency updates | Dependabot weekly `uv` updates |
| Local commit checks | pre-commit hooks |
| Tests | pytest |
| Python lint/format | ruff |
| Python type checking | pyright, aligned with Pylance diagnostics |
| Database migrations | Liquibase |
| Infrastructure as code | Terraform |
| Infrastructure checks | terraform fmt, terraform validate, tflint, checkov |
| CI/CD | GitHub Actions |
| GitHub Actions updates | Dependabot weekly action updates |
| AWS authentication | GitHub OIDC role assumption |
| Secret scanning | Dependency-free high-confidence scanner in `scripts/secret_scan.py` |
| Python dependency audit | `pip-audit` against a frozen `uv.lock` export |
| SAST | GitHub CodeQL for Python |
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
make secret-scan
make dependency-audit
make lint
make fmt
uv run pytest tests/ -v
```

`ruff` and `pyright` are declared in the root development dependency group so
local quality checks do not depend on globally installed binaries. The secret
scanner uses only the Python standard library so it can run in GitHub Actions
without adding another external security service or policy file. The dependency
audit exports the resolved `uv.lock` graph to a temporary requirements file and
runs `pip-audit` against those exact pins.

CodeQL runs in GitHub Actions because its value is in GitHub code scanning
annotations and security tab results, not as a local pre-commit hook.

Dependabot uses the `uv` ecosystem for Python dependency updates and the
`github-actions` ecosystem for workflow action updates.

The app workflow runs Trivy before pushing first-party app, worker, data export,
Liquibase, and mirrored PgBouncer images to ECR. Terraform also enables ECR
scan-on-push for each managed repository.

Base image digest pinning remains deferred until automated digest renewal is
added in the same change. Mutable version tags are less strict, but they avoid
quietly freezing stale base layers without a renewal workflow.

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

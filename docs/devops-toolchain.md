# DevOps Toolchain

This project should demonstrate a complete but lean DevOps toolchain around ECS.

## Current Toolchain

| Concern | Current mechanism |
|---|---|
| Source control | Git monorepo |
| Local orchestration | Docker Compose |
| Standard workstation | Dev Container with pinned project quality tools installed |
| Native macOS workstation | `Brewfile` plus explicit HashiCorp Terraform install |
| Python dependency management | `uv` workspace |
| Python dependency updates | Dependabot weekly `uv` updates |
| Local commit checks | pre-commit hooks |
| Tests | pytest |
| Python lint/format | ruff |
| Python type checking | pyright, aligned with Pylance diagnostics |
| Shell script syntax | `bash -n scripts/*.sh` |
| Documentation links | lychee |
| GitHub workflow linting | actionlint |
| Dockerfile linting | hadolint |
| Database migrations | Liquibase |
| Infrastructure as code | Terraform |
| Infrastructure checks | terraform fmt, terraform validate, tflint, checkov |
| CI/CD | GitHub Actions |
| GitHub Actions updates | Dependabot weekly action updates |
| AWS authentication | GitHub OIDC role assumption |
| Secret scanning | Gitleaks |
| Python dependency audit | Direct `pip-audit` against a frozen `uv.lock` export |
| SAST | Semgrep Community Edition |
| Image registry | ECR |
| Image security | Trivy before push, ECR scanning configured in Terraform |
| Runtime | ECS Fargate |

## Workstation Baseline

Prefer the dev container for exact reproducibility. It pins the daily toolchain
used by the project: Python 3.14, `uv`, Terraform 1.15.0, Go 1.26.2,
Node.js 24 LTS, npm 11.13.0, TypeScript 6.0.3, AWS CLI v2, TFLint, Checkov,
pre-commit, actionlint, lychee, hadolint, gitleaks, and Docker CLI/Compose
access.

For native macOS work, `Brewfile` installs the same mainstream tool families
where Homebrew is the right channel. Terraform is intentionally documented
outside `Brewfile` because HashiCorp's signed release channel is the source of
truth for the exact stable version. Stay on stable releases and avoid preview
or release-candidate builds for project tooling.

## Hardening Goals

- Keep `.pre-commit-config.yaml` aligned with `make lint` and `make fmt`.
- Keep all quality gates runnable locally and in CI.
- Keep AWS-changing workflows split so humans review Terraform plan output or
  build/scan results before triggering apply or deploy.
- Document Bitbucket Pipelines equivalents without maintaining duplicate pipelines.
- Keep scripts small, explicit, and easy to inspect.

## Local Quality Commands

For the most reproducible workstation, open the repository in the dev
container. It is intentionally a development shell, not another app runtime:
the existing Docker Compose services still provide Postgres, PgBouncer,
Liquibase, the API, workers, and data jobs.

```bash
make pre-commit
make secret-scan
make dependency-audit
make lint-scripts
make lint-docs
make lint-workflows
make lint-dockerfiles
make lint
make fmt
uv run pytest tests/ -v
```

`ruff`, `pyright`, and `pip-audit` are declared in the root development
dependency group. Standard ecosystem tools own generic checks: Gitleaks scans
for committed secrets, lychee checks documentation links, actionlint validates
workflow syntax and expressions, and hadolint checks Dockerfile hygiene. The
dependency audit exports the resolved `uv.lock` graph to a temporary
requirements file and runs `pip-audit` against those exact pins.

Pre-commit runs lightweight file hygiene, Ruff, Terraform fmt, shell script
syntax checks, standard docs/workflow/Dockerfile checks, Gitleaks, and Pyright.
Pyright is intentionally included because type regressions are cheap to catch
before commit and have already been a repo-wide quality goal. Network-backed or
slower checks stay in Make and CI: dependency audit, TFLint, Checkov, Semgrep,
Terraform validate/plan, Docker builds, Trivy, and pytest.

Semgrep Community Edition runs in GitHub Actions as the repo's SAST gate. It is
kept out of pre-commit because full-code SAST is slower than the local edit loop
and should run consistently in CI.

SBOM generation remains deferred until a CI upload, registry attachment,
release artifact, or compliance process consumes it. Generating an unused SBOM
would add churn without improving operator behavior.

Security exceptions remain inline in the relevant tool configuration until
there is a real cross-tool exception process. Do not add
`security/exceptions.yaml` as an empty placeholder.

Dependabot uses the `uv` ecosystem for Python dependency updates and the
`github-actions` ecosystem for workflow action updates.

The App Build workflow runs Trivy before pushing first-party app, worker, data
export, Liquibase, and the patched PgBouncer sidecar image to ECR. Terraform
also enables ECR scan-on-push for each managed repository.

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
| Local/operator scripts | Verb-first or domain-first names such as `db_tunnel.sh`, `db_seed_tunnel.sh`, and `seed_data.py`. |

Do not add empty top-level folders from the inspired architecture. Create
`docs/runbooks/`, `docs/drills/`, `security/`, or extra `packages/*` only when
there is real content and
a clear owner.

## Bitbucket Pipelines Equivalence

For interview and documentation purposes, the GitHub Actions workflow maps to
Bitbucket Pipelines as follows:

- `pull_request` workflows map to pull request pipelines.
- `workflow_dispatch` maps to manually triggered custom pipelines.
- Separate plan/build and apply/deploy workflows map to manual approval steps
  without requiring paid environment reviewer features.
- GitHub Environments map to deployment environments.
- GitHub OIDC role assumption maps to Bitbucket OIDC federation with AWS STS.
- Reusable workflow steps map to YAML anchors or shared pipe definitions.

Do not add Bitbucket configuration unless this repo needs to run in Bitbucket.
